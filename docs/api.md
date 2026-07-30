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

**HTML structure:** `<table>` with rows: rank (numeric td), title/link td containing `<a href="/archive.php?m={mount_id}">`, listener count td, status td.

### Search by ICAO: `/search/?icao={ICAO}`

| Param | Description |
|-------|-------------|
| `icao` | 4-char ICAO airport code or ARTCC code, e.g. `KJFK`, `ZNY` |

**HTML structure:**
- One `<table class="body">` per feed containing:
  - `<strong>`: feed title
  - `<font>`: "UP" or "DOWN" status text
  - `<a href="/archive.php?m={mount_id}">`: archive link (source of mount_id)
- One `<table class="freqTable">` per feed (paired by index) containing:
  - Header row `<tr><th>Function</th><th>Frequency</th></tr>`
  - Data rows `<tr><td>Ground</td><td>121.900</td></tr>`

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

**HTML structure:** `<select>` with `<option value="{mount_id}-{YYYYMMDD}-{HHMM}Z.mp3">`.

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
