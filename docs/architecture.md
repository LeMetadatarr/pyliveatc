# Architecture

## Module map

```
pyliveatc/
├── transport.py   — HTTP layer (CF bypass, throttle, env config)
├── models.py      — Frozen dataclasses (Feed, TopFeed, Frequency, ArchiveFile)
├── scraper.py     — HTML parsers for each page; public search/fetch functions
├── archive.py     — Archive listing parser + MP3 downloader
├── dataset.py     — JSONL export + full crawl
└── __main__.py    — CLI dispatcher
```

## Data flow

```
User call          Transport                liveatc.net        Parser        Models
─────────          ─────────                ───────────        ──────        ──────
search("KJFK") → Transport.get_text() → GET /search/?icao=KJFK → parse_search_html() → [Feed, ...]
fetch_topfeeds()→ Transport.get_text() → GET /topfeeds.php      → parse_topfeeds_html()→ [TopFeed, ...]
fetch_archive()→  Transport.get_text() → GET /archive.php?m=... → parse_archive_html()→ [ArchiveFile, ...]
download()     →  Transport.get_bytes()→ GET archive.liveatc.net → write bytes → Path
```

## Transport

`Transport` wraps `unblock_requests.CloudflareSession`. LiveATC.net sits behind Cloudflare managed challenge — `curl_cffi` TLS impersonation is sufficient; JS challenge mode is rare. Rate limiting (default 1.5s between requests) is enforced at `_throttle()`.

## HTML parsing strategy

All three listing pages (`/topfeeds.php`, `/search/`, `/feedindex.php`) share the same table-based HTML structure. Parsers use BeautifulSoup with `lxml` backend:

- Feed block: `table.body` — title in `<strong>`, status in `<font>`, mount_id from `<a href="/archive.php?m=...">` via regex `m=([a-zA-Z0-9_]+)`
- Frequency block: `table.freqTable` — rows paired 1:1 with feed blocks by index

Top feeds page uses a plain `<table>` with numeric rank in the first `<td>`.

## Archive

Archive filenames encode all metadata: `{mount_id}-{YYYYMMDD}-{HHMM}Z.mp3`. The archive page lists them as `<option>` values. The CDN URL is constructed directly without a round-trip: `https://archive.liveatc.net/{mount_id}/{filename}`.
