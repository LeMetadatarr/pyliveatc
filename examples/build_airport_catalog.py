"""Build a JSON catalog of all airports with their feeds and frequencies.

Useful as a static snapshot for offline use, chatbots, or building
a searchable airport database. Writes airports.json.

Catalog schema:
    {
      "KJFK": {
        "icao": "KJFK",
        "feeds": [
          {"mount_id": "kjfk9_s", "title": "...", "up": true,
           "stream_url": "...", "frequencies": [...]}
        ]
      }, ...
    }
"""
import json
import time
from collections import defaultdict
from pathlib import Path

from pyliveatc import iter_all_feeds


def build_catalog(out_path: str = "airports.json") -> dict:
    airports: dict = defaultdict(lambda: {"icao": "", "feeds": []})

    for feed in iter_all_feeds():
        icao = feed.icao or feed.mount_id[:4].upper()
        airports[icao]["icao"] = icao
        airports[icao]["feeds"].append(feed.to_dict())
        time.sleep(0.0)  # iter_all_feeds has built-in throttling

    catalog = dict(sorted(airports.items()))
    Path(out_path).write_text(json.dumps(catalog, indent=2, ensure_ascii=False))
    print(f"Catalog: {len(catalog)} airports, {sum(len(v['feeds']) for v in catalog.values())} feeds")
    print(f"Saved to {out_path}")
    return catalog


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="airports.json")
    args = parser.parse_args()
    catalog = build_catalog(args.out)

    # Show top 10 airports by feed count
    by_feeds = sorted(catalog.items(), key=lambda kv: len(kv[1]["feeds"]), reverse=True)
    print("\nTop 10 airports by feed count:")
    for icao, data in by_feeds[:10]:
        online = sum(1 for f in data["feeds"] if f["up"])
        print(f"  {icao}  {len(data['feeds'])} feeds ({online} online)")
