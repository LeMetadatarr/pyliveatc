# Usage

## Install

```bash
pip install pyliveatc
pip install "pyliveatc[stealth]"   # add curl-cffi TLS impersonation (recommended)
pip install "pyliveatc[anon]"      # add IP rotation
```

## Search by airport

```python
from pyliveatc import search

feeds = search("KJFK")
for feed in feeds:
    print(feed.title, feed.stream_url, "UP" if feed.up else "DOWN")
    for freq in feed.frequencies:
        print(f"  {freq.title}: {freq.frequency}")
```

## Top feeds

```python
from pyliveatc import fetch_topfeeds

for tf in fetch_topfeeds():
    print(f"#{tf.rank} {tf.title}: {tf.listener_count} listeners")
```

## Browse by category

```python
from pyliveatc import fetch_feedindex, FEED_TYPES

print(FEED_TYPES)
# ['all', 'class-b', 'class-d', 'us-artcc', 'international-eu', ...]

feeds = fetch_feedindex("international-eu")
for f in feeds:
    print(f.icao, f.title)
```

## Archive listing

```python
from pyliveatc import fetch_archive_listing

files = fetch_archive_listing("kjfk_app")
for af in files[:5]:
    print(af.filename, af.url)
```

## Resolve the live stream URL

```python
from pyliveatc import get_stream_url

url = get_stream_url("kjfk_gnd", icao="kjfk")
# "https://s1-bos.liveatc.net/kjfk_gnd" (or None if the page was
# unreachable/unparseable — see the Access notes in transport.py)
```

## List archived facilities

```python
from pyliveatc import list_archive_facilities

for facility in list_archive_facilities()[:5]:
    print(facility["display_name"], facility["facility_key"])
```

## Download archive audio

```python
from pyliveatc import download_range

paths = download_range(
    mount_id="kjfk_app",
    date="20260609",    # YYYYMMDD
    hours=[12, 13],     # UTC hours, each yields 2 x 30-min files
    dest_dir="./audio",
)
for p in paths:
    print(p)
```

## Custom transport

```python
from pyliveatc import Transport, search

t = Transport(mode="curl_cffi", anon=True)
feeds = search("EGLL", transport=t)
t.close()
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `PYLIVEATC_MODE` | `curl_cffi` | Transport mode: `curl_cffi`, `requests`, `flaresolverr`, `wayback` |
| `PYLIVEATC_ANON` | unset | Set to `1` to enable IP rotation |
| `PYLIVEATC_DELAY` | `1.5` | Seconds between requests |
| `PYLIVEATC_FLARESOLVERR` | `http://localhost:8191` | FlareSolverr URL (without trailing `/v1`) |

---
[← API](api.md) · [Home](README.md) · [Architecture →](architecture.md)
