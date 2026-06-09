"""Batch download the last 24 hours of audio from multiple feeds.

Demonstrates download_range() across several airports in parallel-ish fashion.
"""
import argparse
import time
from datetime import date, timedelta
from pathlib import Path

from pyliveatc import download_range, search

# Feeds to download: (label, mount_id, date_str, hours)
TARGETS = [
    ("KJFK Approach", "kjfk9_s"),
    ("EGLL Tower", "egll_twr"),
    ("RJTT Control", "rjtt_control"),
]

HOURS_UTC = list(range(0, 24))   # full day — trim as needed


def run(out_dir: str, date_str: str, hours: list):
    out = Path(out_dir)
    total_files = 0
    for label, mount_id in TARGETS:
        dest = out / mount_id
        print(f"\n[{label}] mount={mount_id}  date={date_str}  hours={hours[:3]}...")
        paths = download_range(mount_id=mount_id, date=date_str, hours=hours, dest_dir=str(dest))
        print(f"  → {len(paths)} files saved to {dest}")
        for p in paths[:3]:
            print(f"     {p.name}  {p.stat().st_size:,} bytes")
        total_files += len(paths)
        time.sleep(1.0)
    print(f"\nTotal files downloaded: {total_files}")


if __name__ == "__main__":
    yesterday = (date.today() - timedelta(days=1)).strftime("%Y%m%d")
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="./atc_batch")
    parser.add_argument("--date", default=yesterday)
    parser.add_argument("--hours", nargs="+", type=int, default=[0, 1, 2])
    args = parser.parse_args()
    run(args.out, args.date, args.hours)
