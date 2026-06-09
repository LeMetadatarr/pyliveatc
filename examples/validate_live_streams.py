"""Validate live stream downloading via FlareSolverr.

Usage::

    PYLIVEATC_MODE=flaresolverr \
    PYLIVEATC_FLARESOLVERR=http://192.168.1.116:8191 \
    python examples/validate_live_streams.py [ICAO [ICAO ...]]

Downloads 30 seconds of live audio from the first UP feed found for each
ICAO code and saves it to /tmp/liveatc_validate/.  Prints byte counts and
confirms the data starts with a valid MP3 or MPEG-audio frame header.
"""
import os
import sys
import time
from pathlib import Path

DEST_DIR = Path("/tmp/liveatc_validate")
DEST_DIR.mkdir(parents=True, exist_ok=True)

# Default to a few well-known busy airports if none given
ICAO_LIST = sys.argv[1:] or ["KJFK", "KLAX", "EGLL"]
RECORD_SECONDS = 30


def is_mp3(data: bytes) -> bool:
    """Check for MP3 sync word (0xFF 0xE0 mask) or ID3 header."""
    if data[:3] == b"ID3":
        return True
    if len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        return True
    return False


def main():
    import pyliveatc
    from pyliveatc.transport import Transport

    mode = os.environ.get("PYLIVEATC_MODE", "curl_cffi")
    fs_url = os.environ.get("PYLIVEATC_FLARESOLVERR", "http://192.168.1.116:8191")
    print(f"Transport mode : {mode}")
    if mode == "flaresolverr":
        print(f"FlareSolverr   : {fs_url}")
    print()

    t = Transport(mode=mode, flaresolverr_url=fs_url)

    results = []
    for icao in ICAO_LIST:
        print(f"[{icao}] Searching feeds …")
        try:
            feeds = pyliveatc.search(icao, transport=t)
        except Exception as exc:
            print(f"  ERROR fetching feeds: {exc}")
            results.append({"icao": icao, "ok": False, "error": str(exc)})
            continue

        up_feeds = [f for f in feeds if f.up]
        if not up_feeds:
            up_feeds = feeds  # fallback: try even if reported DOWN

        if not feeds:
            print(f"  No feeds found for {icao}")
            results.append({"icao": icao, "ok": False, "error": "no feeds"})
            continue

        feed = up_feeds[0]
        print(f"  Feed: {feed.title!r}  mount={feed.mount_id}  up={feed.up}")

        # Resolve the real streaming server via hlisten.php
        print(f"  Resolving stream URL …")
        stream_url = pyliveatc.get_stream_url(feed.mount_id, feed.icao, transport=t)
        if stream_url:
            print(f"  Stream URL : {stream_url}")
        else:
            stream_url = f"https://d.liveatc.net/{feed.mount_id}"
            print(f"  (hlisten.php lookup failed; using fallback: {stream_url})")

        # Record audio
        dest = DEST_DIR / f"{feed.mount_id}_{int(time.time())}.mp3"
        print(f"  Recording {RECORD_SECONDS}s → {dest} …")
        try:
            nbytes = pyliveatc.stream_live(feed.mount_id, str(dest),
                                           seconds=RECORD_SECONDS, transport=t)
        except Exception as exc:
            # Fallback: use transport.stream_bytes() for just a snippet
            print(f"  stream_live failed ({exc}); trying stream_bytes() snippet …")
            try:
                data = t.stream_bytes(stream_url, nbytes=65536)
                dest.write_bytes(data)
                nbytes = len(data)
            except Exception as exc2:
                print(f"  stream_bytes also failed: {exc2}")
                results.append({"icao": icao, "ok": False, "error": str(exc2)})
                continue

        data_head = dest.read_bytes()[:16] if dest.exists() else b""
        mp3_ok = is_mp3(data_head)
        print(f"  Written     : {nbytes:,} bytes")
        print(f"  Header hex  : {data_head[:8].hex()}")
        print(f"  Valid MP3   : {'YES ✓' if mp3_ok else 'NO (may be AAC/Ogg/raw MPEG)'}")
        results.append({
            "icao": icao,
            "mount_id": feed.mount_id,
            "title": feed.title,
            "stream_url": stream_url,
            "dest": str(dest),
            "bytes": nbytes,
            "mp3_ok": mp3_ok,
            "ok": True,
        })
        print()

    # ── Summary ──────────────────────────────────────────────────────────
    print("=" * 60)
    print("  Validation Summary")
    print("=" * 60)
    for r in results:
        status = "OK" if r.get("ok") else "FAIL"
        if r.get("ok"):
            print(f"  [{status}] {r['icao']:6s}  {r['bytes']:7,} bytes  {r.get('dest','')}")
        else:
            print(f"  [{status}] {r['icao']:6s}  {r.get('error')}")
    print("=" * 60)
    ok_count = sum(1 for r in results if r.get("ok"))
    print(f"\n  {ok_count}/{len(results)} airports validated successfully")
    if ok_count < len(results):
        sys.exit(1)


if __name__ == "__main__":
    main()
