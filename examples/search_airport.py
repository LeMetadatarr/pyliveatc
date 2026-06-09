"""Search for all feeds at an airport by ICAO code."""
from pyliveatc import search

feeds = search("KJFK")
print(f"Found {len(feeds)} feeds for KJFK\n")

for feed in feeds:
    status = "UP  " if feed.up else "DOWN"
    print(f"[{status}] {feed.title}")
    print(f"         stream : {feed.stream_url}")
    print(f"         archive: {feed.archive_url}")
    for freq in feed.frequencies:
        print(f"         {freq.title:15s} {freq.frequency}")
    print()
