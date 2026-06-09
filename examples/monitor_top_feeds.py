"""Poll top-50 feeds every N minutes and log listener trends.

Writes a JSONL log that can be used to track which feeds surge
during weather events, incidents, or peak traffic hours.

Usage::

    python examples/monitor_top_feeds.py --interval 300 --out ./top_monitor.jsonl
    # Ctrl+C to stop
"""
import argparse
import json
import signal
import sys
import time
from datetime import datetime, timezone

from pyliveatc import fetch_topfeeds


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def poll(out_path: str, interval_s: int):
    stop = False

    def handle(sig, frame):
        nonlocal stop
        stop = True
        print("\nStopping.")

    signal.signal(signal.SIGINT, handle)

    with open(out_path, "a", encoding="utf-8") as fh:
        print(f"Polling every {interval_s}s → {out_path}  (Ctrl+C to stop)")
        while not stop:
            ts = now_utc()
            try:
                feeds = fetch_topfeeds()
                row = {
                    "timestamp": ts,
                    "feeds": [{"rank": f.rank, "mount_id": f.mount_id,
                               "listeners": f.listener_count, "title": f.title}
                              for f in feeds],
                }
                fh.write(json.dumps(row) + "\n")
                fh.flush()
                top3 = ", ".join(f"#{f.rank} {f.mount_id}={f.listener_count}" for f in feeds[:3])
                print(f"[{ts}] Top 3: {top3}")
            except Exception as e:
                print(f"[{ts}] Error: {e}")
            if not stop:
                time.sleep(interval_s)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=300, help="Poll interval in seconds")
    parser.add_argument("--out", default="./top_monitor.jsonl")
    args = parser.parse_args()
    poll(args.out, args.interval)
