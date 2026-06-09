"""Search feeds by frequency across all airports.

Demonstrates scanning the full feed catalog to find which feeds
use a given ATC frequency — useful for tuning to a specific sector.

Usage::

    python examples/frequency_search.py 121.500   # emergency frequency
    python examples/frequency_search.py 123.900
"""
import argparse
import re
from pyliveatc import iter_all_feeds


def find_by_frequency(target_freq: str) -> list:
    """Return all feeds that carry the given frequency."""
    hits = []
    norm = target_freq.strip().lstrip("0")
    for feed in iter_all_feeds():
        for freq in feed.frequencies:
            if freq.frequency.lstrip("0") == norm or freq.frequency == target_freq:
                hits.append((feed, freq))
    return hits


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("frequency", help="ATC frequency to search, e.g. 121.500")
    args = parser.parse_args()

    print(f"Searching for feeds on {args.frequency} MHz ...\n")
    hits = find_by_frequency(args.frequency)

    if not hits:
        print("No feeds found for that frequency.")
    else:
        print(f"Found {len(hits)} feed(s):\n")
        for feed, freq in hits:
            status = "UP  " if feed.up else "DOWN"
            print(f"  [{status}] {feed.title}")
            print(f"           {freq.title} — {freq.frequency} MHz")
            print(f"           stream: {feed.stream_url}")
