# LiveATC.net API Reference (Reverse-Engineered)

## Base URLs

| Base | Purpose |
|------|---------|
| `https://www.liveatc.net` | Main site (Cloudflare-protected) |
| `https://archive.liveatc.net` | Archive MP3 files (direct CDN) |
| `http://d.liveatc.net` | Live Icecast2 MP3 streams |

## Pages

### Top Feeds: `/topfeeds.php`

No parameters. Lists top-50 feeds by current listener count.

**HTML structure:** `<table class="topTable">` with rows: rank (numeric td),
listener count td, title/link td. The title link no longer points at
`archive.php?m=...` — the mount id is only present as the first argument of
the play button's `onclick="myHTML5Popup('{mount_id}','{icao}')"` handler.
`parse_topfeeds_html()` reads the mount id from that handler, falling back
to an `archive.php?m=...` link if present, so it also accepts the older
page layout.

### Search by ICAO: `/search/?icao={ICAO}`

| Param | Description |
|-------|-------------|
| `icao` | 4-char ICAO airport code or ARTCC code, e.g. `KJFK`, `ZNY` |

**HTML structure:**
- One `<table class="body">` per feed containing:
  - `<strong>`: feed title
  - `<font>`: "UP" or "DOWN" status text
  - `<a href="/archive.php?m={mount_id}">`: archive link (source of mount_id)
- One `<table class="freqTable">` per feed containing:
  - Header row `<tr><th>Function</th><th>Frequency</th></tr>`
  - Data rows `<tr><td>Ground</td><td>121.900</td></tr>`

Station rows without a `<strong>` title (spacer rows) are interspersed
among real feed rows and carry no `freqTable`. `parse_search_html()` pairs
each kept feed with the next `freqTable` in document order — not by the
station's raw position in the page — so spacer rows don't shift every
frequency table after them out of alignment.

### Feed Index: `/feedindex.php?type={type}`

| `type` value | Description |
|---|---|
| `all` | All feeds |
| `class-b` | US Class B airports |
| `class-d` | US Class D airports |
| `us-artcc` | US ARTCC Center feeds |
| `international-eu` | Europe airports |
| `international-as` | Asia airports |
| `hf` | HF/Shortwave oceanic |
| `canada` | Canadian airports |

Same HTML structure as `/search/`.

### Archive Listing: `/archive.php?m={mount_id}`

| Param | Description |
|-------|-------------|
| `m` | Mount point identifier, e.g. `kjfk_app` |

**HTML structure:** historically a `<select>` with
`<option value="{mount_id}-{YYYYMMDD}-{HHMM}Z.mp3">`, which
`parse_archive_html()` still supports. The current live page instead only
exposes a `facility` / `time` `<select>` form (facility keys like
`KJFK-GndTwr`, not mount ids) that must be POSTed through a
Turnstile-protected flow to resolve a download link — see
`pyliveatc/archive.py`'s module docstring. Against the current page,
`parse_archive_html()` correctly returns an empty list rather than
fabricating URLs; direct archive downloads instead rely on the
well-known CDN URL pattern below.

## Archive CDN

Direct MP3 URL pattern:
```
https://archive.liveatc.net/{mount_id}/{mount_id}-{YYYYMMDD}-{HHMM}Z.mp3
```

Files are 30-minute segments. Hours run from 0000Z to 2330Z.

## Live Stream

Direct Icecast2 stream:
```
http://d.liveatc.net/{mount_id}
```

Audio format: MP3, 16 kbps CBR, 22050 Hz, mono.

## Mount ID Format

Mount IDs follow the pattern `{icao}_{function}`, for example:
- `kjfk_app`: KJFK Approach/Departure
- `kjfk_gnd_twr`: KJFK Ground/Tower
- `klax_south_tower`: KLAX South Tower
- `egll_tower`: EGLL (Heathrow) Tower

The ICAO prefix is the first 4 characters.

---
[Home](README.md) · [Usage →](usage.md)
