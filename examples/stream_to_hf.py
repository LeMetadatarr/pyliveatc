"""Continuously record live ATC audio and push chunks directly to Hugging Face.

Records N_WORKERS feeds in parallel, each in CHUNK_SECONDS chunks.  Each
chunk is uploaded to a HF dataset repo as soon as it is recorded, then the
local temp file is deleted.  No persistent local disk needed.

Dataset layout on HF::

    data/
      {region}/{mount_id}/{mount_id}_{YYYYMMDD_HHMMSS}Z.mp3
    metadata.jsonl   ← appended every commit

Usage::

    pip install huggingface_hub
    export HF_TOKEN=hf_...
    export PYLIVEATC_MODE=flaresolverr
    export PYLIVEATC_FLARESOLVERR=http://192.168.1.116:8191

    python examples/stream_to_hf.py [--repo TigreGotico/liveatc-atc-audio] \\
                                     [--workers 8] [--chunk 300]

Stop with Ctrl-C; already-uploaded chunks are preserved on HF.
"""
import argparse
import json
import logging
import os
import queue
import re
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("liveatc-hf")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ICAO_RE = re.compile(r"^([A-Z]{4})", re.I)

_REGION_MAP = {
    "K": "usa", "C": "canada",
    "E": "europe", "L": "europe",
    "B": "europe", "D": "europe",
    "R": "japan_korea",
    "Y": "australia",
    "Z": "china",
    "V": "asia",
    "U": "russia",
    "F": "africa",
    "S": "south_america",
    "M": "central_america",
    "P": "pacific",
}


def _region(name: str) -> str:
    m = ICAO_RE.match(name.strip())
    if not m:
        return "other"
    return _REGION_MAP.get(m.group(1)[0].upper(), "other")


def _load_mount_ids() -> list:
    """Return a list of (mount_id, display_name, region) tuples."""
    cache = Path("/tmp/liveatc_cache.json")
    if not cache.exists():
        log.info("Fetching facility list from liveatc.net …")
        from pyliveatc.archive import list_archive_facilities
        from pyliveatc.transport import Transport
        t = Transport()
        facs = list_archive_facilities(transport=t)
        facilities = [[f["facility_key"], f["display_name"]] for f in facs]
        cache.write_text(json.dumps({"facilities": facilities, "topfeeds": []}))
    else:
        data = json.loads(cache.read_text())
        facilities = data["facilities"]

    result = []
    for key, name in facilities:
        if not key:
            continue
        result.append((key, name, _region(name)))
    return result


def _diverse_cycle(mount_ids: list) -> "generator":
    """Round-robin across regions so the dataset stays geographically diverse."""
    by_region: dict = {}
    for mid, name, region in mount_ids:
        by_region.setdefault(region, []).append((mid, name))

    # interleave: one from each region per round
    region_iters = {r: iter(entries) for r, entries in by_region.items()}
    while True:
        exhausted = []
        for region, it in list(region_iters.items()):
            try:
                mid, name = next(it)
                yield mid, name, region
            except StopIteration:
                exhausted.append(region)
                # restart the iterator for that region
                region_iters[region] = iter(by_region[region])
                mid, name = next(region_iters[region])
                yield mid, name, region


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

_stop_event = threading.Event()


def _worker(feed_queue: queue.Queue, api, repo_id: str,
            chunk_seconds: int, stats: dict, stats_lock: threading.Lock):
    """Pull mount IDs from queue, record, upload, repeat."""
    from curl_cffi.requests import Session as CurlSession

    while not _stop_event.is_set():
        try:
            mount_id, display_name, region = feed_queue.get(timeout=2)
        except queue.Empty:
            continue

        stream_url = f"https://d.liveatc.net/{mount_id}"
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path_in_repo = f"data/{region}/{mount_id}/{mount_id}_{ts}Z.mp3"

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            log.info("REC  %-35s → %s  (%ds)", mount_id, path_in_repo, chunk_seconds)
            nbytes = _record(stream_url, tmp_path, chunk_seconds)
            if nbytes < 4096:
                log.warning("SKIP %-35s — only %d bytes (feed down?)", mount_id, nbytes)
                feed_queue.task_done()
                continue

            log.info("PUSH %-35s  %d KB", mount_id, nbytes // 1024)
            api.upload_file(
                path_or_fileobj=str(tmp_path),
                path_in_repo=path_in_repo,
                repo_id=repo_id,
                repo_type="dataset",
                commit_message=f"add {mount_id} {ts}",
            )

            # Append metadata row
            row = json.dumps({
                "file": path_in_repo,
                "mount_id": mount_id,
                "display_name": display_name,
                "region": region,
                "recorded_utc": ts,
                "duration_s": chunk_seconds,
                "bytes": nbytes,
            })
            _append_metadata(api, repo_id, row)

            with stats_lock:
                stats["chunks"] += 1
                stats["bytes"] += nbytes
                stats["hours"] = stats["bytes"] / (16_000 / 8) / 3600
            log.info("OK   %-35s  total %.2fh audio uploaded",
                     mount_id, stats["hours"])

        except Exception as exc:
            log.error("ERR  %-35s  %s", mount_id, exc)
        finally:
            tmp_path.unlink(missing_ok=True)
            feed_queue.task_done()


def _record(url: str, dest: Path, seconds: int) -> int:
    from curl_cffi.requests import Session as CurlSession
    import time as _time
    session = CurlSession(impersonate="chrome")
    r = session.get(url, stream=True)
    r.raise_for_status()
    total = 0
    deadline = _time.monotonic() + seconds
    with open(dest, "wb") as fh:
        for chunk in r.iter_content(chunk_size=4096):
            if not chunk:
                continue
            fh.write(chunk)
            total += len(chunk)
            if _time.monotonic() >= deadline:
                break
    r.close()
    return total


_meta_buffer: list = []
_meta_lock = threading.Lock()
_META_FLUSH_EVERY = 10  # flush to HF every N rows


def _append_metadata(api, repo_id: str, row: str):
    """Buffer metadata rows; flush to HF every N rows to reduce API calls."""
    with _meta_lock:
        _meta_buffer.append(row)
        if len(_meta_buffer) < _META_FLUSH_EVERY:
            return
        _flush_metadata(api, repo_id)


def _flush_metadata(api, repo_id: str):
    """Upload buffered metadata rows (caller must hold _meta_lock)."""
    if not _meta_buffer:
        return
    rows = "\n".join(_meta_buffer) + "\n"
    _meta_buffer.clear()
    try:
        existing = api.hf_hub_download(
            repo_id=repo_id, filename="metadata.jsonl",
            repo_type="dataset", force_download=True,
        )
        rows = Path(existing).read_text().rstrip("\n") + "\n" + rows
    except Exception:
        pass
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write(rows)
        meta_tmp = f.name
    try:
        api.upload_file(
            path_or_fileobj=meta_tmp,
            path_in_repo="metadata.jsonl",
            repo_id=repo_id,
            repo_type="dataset",
            commit_message=f"update metadata ({len(rows.splitlines())} rows)",
        )
    finally:
        Path(meta_tmp).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default="TigreGotico/liveatc-atc-audio",
                        help="HF dataset repo id")
    parser.add_argument("--workers", type=int, default=8,
                        help="Parallel recording threads")
    parser.add_argument("--chunk", type=int, default=300,
                        help="Seconds per audio chunk (default 300 = 5 min)")
    parser.add_argument("--target-hours", type=float, default=0,
                        help="Stop after this many hours of audio (0 = run forever)")
    args = parser.parse_args()

    token = os.environ.get("HF_TOKEN")
    if not token:
        raise SystemExit("Set HF_TOKEN env var to your Hugging Face write token.")

    from huggingface_hub import HfApi
    api = HfApi(token=token)

    # Create repo if it doesn't exist
    try:
        api.create_repo(repo_id=args.repo, repo_type="dataset",
                        private=True, exist_ok=True)
        log.info("Dataset repo: https://huggingface.co/datasets/%s", args.repo)
    except Exception as exc:
        log.warning("create_repo: %s (continuing)", exc)

    # Build feed queue (infinite generator via a refill thread)
    mount_ids = _load_mount_ids()
    log.info("Loaded %d mount IDs", len(mount_ids))
    feed_q: queue.Queue = queue.Queue(maxsize=args.workers * 4)

    def _filler():
        for item in _diverse_cycle(mount_ids):
            if _stop_event.is_set():
                break
            feed_q.put(item)

    filler = threading.Thread(target=_filler, daemon=True, name="filler")
    filler.start()

    stats = {"chunks": 0, "bytes": 0, "hours": 0.0}
    stats_lock = threading.Lock()

    threads = []
    for i in range(args.workers):
        t = threading.Thread(
            target=_worker,
            args=(feed_q, api, args.repo, args.chunk, stats, stats_lock),
            daemon=True,
            name=f"worker-{i}",
        )
        t.start()
        threads.append(t)

    log.info("Started %d workers — Ctrl-C to stop", args.workers)
    try:
        while True:
            time.sleep(30)
            with stats_lock:
                h = stats["hours"]
                n = stats["chunks"]
            log.info("STATUS  %d chunks  %.2fh audio uploaded", n, h)
            if args.target_hours > 0 and h >= args.target_hours:
                log.info("Reached target %.1fh — stopping", args.target_hours)
                break
    except KeyboardInterrupt:
        log.info("Interrupted — stopping workers …")
    finally:
        _stop_event.set()
        for t in threads:
            t.join(timeout=10)
        # flush any remaining metadata rows
        with _meta_lock:
            _flush_metadata(api, args.repo)
        with stats_lock:
            log.info("Done. %d chunks, %.2fh audio pushed to %s",
                     stats["chunks"], stats["hours"], args.repo)


if __name__ == "__main__":
    main()
