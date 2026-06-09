---
name: pyliveatc
description: LiveATC.net client — search ATC feeds by airport, browse live streams, list and download archived ATC audio
---
# pyliveatc

Agent-as-ears: programmatic access to live and archived Air Traffic Control audio for deaf/hard-of-hearing users, voice assistants, and accessibility tools.

## When to use

- "Find the JFK tower frequency / stream"
- "What ATC feeds does LAX have?"
- "List all European ATC feeds"
- "Download the last hour of KJFK approach audio"
- "Which ATC feeds are most popular right now?"

## Install

```bash
pip install pyliveatc
```

## Core operations

### `search(icao) -> list[Feed]`

```python
from pyliveatc import search
feeds = search("KJFK")
for f in feeds:
    print(f.title, f.stream_url, "live" if f.up else "offline")
    for freq in f.frequencies:
        print(f"  {freq.title}: {freq.frequency} MHz")
```

### `fetch_topfeeds() -> list[TopFeed]`

```python
from pyliveatc import fetch_topfeeds
for tf in fetch_topfeeds():
    print(f"#{tf.rank} {tf.title} ({tf.listener_count} listeners)")
```

### `fetch_feedindex(feed_type) -> list[Feed]`

```python
from pyliveatc import fetch_feedindex
feeds = fetch_feedindex("international-eu")
```

Feed types: `all`, `class-b`, `class-d`, `us-artcc`, `international-eu`, `international-as`, `hf`, `canada`

### `fetch_archive_listing(mount_id) -> list[ArchiveFile]`

```python
from pyliveatc import fetch_archive_listing
files = fetch_archive_listing("kjfk_app")
for af in files[:5]:
    print(af.filename, af.url)
```

### `download_range(mount_id, date, hours, dest_dir) -> list[Path]`

```python
from pyliveatc import download_range
paths = download_range("kjfk_app", "20260609", hours=[12], dest_dir="./audio")
```

## Key fields

**Feed:** `mount_id`, `title`, `icao`, `up` (bool), `stream_url`, `archive_url`, `frequencies`

**TopFeed:** adds `rank` and `listener_count`

**ArchiveFile:** `mount_id`, `filename`, `date`, `time`, `url`

**Frequency:** `title` (e.g. "Tower"), `frequency` (e.g. "119.100")

## Access notes

- LiveATC.net is free to access; no API key required
- Cloudflare-protected — requires `unblock_requests` (bundled dependency)
- Rate-limit: 1.5s between requests by default (`PYLIVEATC_DELAY` env var)
- Live streams at `http://d.liveatc.net/{mount_id}` are Icecast2 MP3 (16 kbps, 22050 Hz, mono)
- Archive files are 30-minute segments at `https://archive.liveatc.net/`
- Third-party embedding of live streams is prohibited per LiveATC ToS; use for personal/research access

## Speaking results (accessibility)

```python
feeds = search("KJFK")
for f in feeds:
    status = "online" if f.up else "offline"
    freqs = ", ".join(f"{fr.title} on {fr.frequency}" for fr in f.frequencies)
    print(f"{f.title} is {status}. Frequencies: {freqs}. Stream: {f.stream_url}")
```
