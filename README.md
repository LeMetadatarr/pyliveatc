# pyliveatc

pyliveatc is a Python client library for [LiveATC.net](https://www.liveatc.net). It finds and downloads live and archived Air Traffic Control audio feeds.

## Features

- Search feeds by ICAO airport code or ARTCC code.
- Browse top feeds by live listener count.
- Browse feeds by category (Class B/D, ARTCC, Europe, Asia, HF, Canada).
- List and download archived 30-minute MP3 segments.
- Export the feed catalog and archive inventory to JSONL for ML and dataset use.

## Install

```bash
pip install pyliveatc
pip install "pyliveatc[stealth]"   # recommended: curl-cffi TLS impersonation for CF bypass
```

## Usage

```python
from pyliveatc import search, fetch_topfeeds, download_range

# Find feeds for an airport
for feed in search("KJFK"):
    print(feed.title, "-", feed.stream_url)

# Top feeds by listeners
for tf in fetch_topfeeds()[:5]:
    print(f"#{tf.rank} {tf.title} ({tf.listener_count} listeners)")

# Download last hour of approach audio
paths = download_range("kjfk_app", "20260609", hours=[12], dest_dir="./audio")
```

## CLI

```bash
python -m pyliveatc search KJFK
python -m pyliveatc topfeeds
python -m pyliveatc feedindex --type international-eu
python -m pyliveatc archive kjfk_app
python -m pyliveatc download kjfk_app --date 20260609 --hours 12 --dest ./audio
python -m pyliveatc dataset --out ./data --types class-b
```

## Docs

See [`docs/`](docs/) for the full API reference, usage examples, architecture notes, and dataset documentation.

## Related projects

- [LeMetadatarr/unblock_requests](https://github.com/LeMetadatarr/unblock_requests): the `requests.Session` subclass pyliveatc uses to bypass Cloudflare.
- [LeMetadatarr/anon_requests](https://github.com/LeMetadatarr/anon_requests): the optional anonymity layer behind the `anon` extra's IP rotation.

## License

Apache-2.0
