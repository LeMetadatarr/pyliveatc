"""Upload locally-scraped LiveATC archive files to a HuggingFace dataset.

Scans a directory tree of M4A files produced by archive_scraper.py and
uploads each one to HF, maintaining the data/{region}/{facility_key}/
layout.  Skips files already present in the repo.

Usage::

    pip install huggingface_hub
    HF_TOKEN=hf_... python3 upload_archive_to_hf.py \\
        --src /home/miro/.config/flaresolver/atc_archive \\
        --repo TigreGotico/liveatc-atc-audio-archive \\
        --workers 8

The --src dir may contain shard_0/ … shard_3/ subdirectories from the
parallel scraper; the script descends into them automatically.
"""
import argparse
import logging
import os
import re
import threading
from pathlib import Path
from queue import Queue, Empty

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("liveatc-upload")

_REGION_MAP = {
    "K": "usa", "C": "canada",
    "E": "europe", "L": "europe", "B": "europe", "D": "europe",
    "R": "japan_korea", "Y": "australia", "Z": "china",
    "V": "asia", "U": "russia", "F": "africa",
    "S": "south_america", "M": "central_america", "P": "pacific",
}
_ICAO_RE = re.compile(r"^([A-Z]{4})", re.I)


def _region(facility_key: str) -> str:
    m = _ICAO_RE.match(facility_key.strip())
    return _REGION_MAP.get(m.group(1)[0].upper(), "other") if m else "other"


def _facility_key_from_filename(name: str) -> str:
    # e.g. KJFK-Del3-Jun-08-2026-1200Z.m4a → KJFK-Del3
    parts = name.split("-")
    # The facility key is everything before the month name (3-letter month)
    months = {"Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"}
    for i, part in enumerate(parts):
        if part[:3].capitalize() in months:
            return "-".join(parts[:i])
    return parts[0]


def _collect_files(src: Path) -> list[Path]:
    files = sorted(src.rglob("*.m4a"))
    log.info("Found %d M4A files under %s", len(files), src)
    return files


def _get_existing(api, repo_id: str) -> set[str]:
    try:
        files = api.list_repo_files(repo_id=repo_id, repo_type="dataset")
        existing = {f for f in files if f.endswith(".m4a")}
        log.info("%d files already in repo", len(existing))
        return existing
    except Exception:
        return set()


def _worker(q: Queue, api, repo_id: str, existing: set, stats: dict, lock: threading.Lock):
    while True:
        try:
            local_path, path_in_repo = q.get(timeout=5)
        except Empty:
            break

        if path_in_repo in existing:
            log.debug("SKIP %s (exists)", path_in_repo)
            q.task_done()
            continue

        nbytes = local_path.stat().st_size
        try:
            api.upload_file(
                path_or_fileobj=str(local_path),
                path_in_repo=path_in_repo,
                repo_id=repo_id, repo_type="dataset",
                commit_message=f"add {local_path.name}",
            )
            with lock:
                stats["ok"] += 1
                stats["bytes"] += nbytes
            log.info("UP %s  %d KB  total=%.1f MB",
                     local_path.name, nbytes // 1024, stats["bytes"] / 1e6)
        except Exception as exc:
            log.error("ERR %s: %s", local_path.name, exc)
            with lock:
                stats["err"] += 1

        q.task_done()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="Directory with downloaded M4A files")
    ap.add_argument("--repo", default="TigreGotico/liveatc-atc-audio-archive")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    token = os.environ.get("HF_TOKEN")
    if not token:
        raise SystemExit("Set HF_TOKEN")

    from huggingface_hub import HfApi
    api = HfApi(token=token)
    api.create_repo(repo_id=args.repo, repo_type="dataset", private=True, exist_ok=True)

    src = Path(args.src)
    files = _collect_files(src)
    existing = _get_existing(api, args.repo)

    q: Queue = Queue()
    for f in files:
        fk = _facility_key_from_filename(f.name)
        region = _region(fk)
        path_in_repo = f"data/{region}/{fk}/{f.name}"
        q.put((f, path_in_repo))

    log.info("Queued %d files (%d already in repo)", q.qsize(), len(existing))

    stats = {"ok": 0, "bytes": 0, "err": 0}
    lock = threading.Lock()
    threads = [
        threading.Thread(target=_worker, args=(q, api, args.repo, existing, stats, lock),
                         daemon=True, name=f"up-{i}")
        for i in range(args.workers)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    log.info("Done. %d uploaded  %d errors  %.1f MB",
             stats["ok"], stats["err"], stats["bytes"] / 1e6)


if __name__ == "__main__":
    main()
