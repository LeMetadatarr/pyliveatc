"""Iterate over every feed across all feed types and print a summary.

Demonstrates iter_all_feeds() with deduplication across categories.
"""
from collections import Counter
from pyliveatc import iter_all_feeds

feeds = list(iter_all_feeds())

print(f"Total unique feeds: {len(feeds)}")
print(f"  Online  : {sum(1 for f in feeds if f.up)}")
print(f"  Offline : {sum(1 for f in feeds if not f.up)}")

regions = Counter()
for f in feeds:
    p = f.icao[0].upper() if f.icao else "?"
    if p == "K":
        regions["USA"] += 1
    elif p == "C":
        regions["Canada"] += 1
    elif p in ("E", "L", "B", "D"):
        regions["Europe"] += 1
    else:
        regions["Other"] += 1

print("\nRegion summary:")
for region, count in regions.most_common():
    print(f"  {region:10s}  {count}")
