# Changelog

## [0.1.0]

- Initial release
- Feed search by ICAO (`search()`)
- Top-50 feeds by listener count (`fetch_topfeeds()`)
- Feed index by category (`fetch_feedindex()`, `iter_feedindex()`, `iter_all_feeds()`)
- Archive listing (`fetch_archive_listing()`) and download (`download_range()`)
- JSONL dataset export (`export_all()`)
- CLI: `search`, `topfeeds`, `feedindex`, `archive`, `download`, `dataset`
- Transport: `unblock_requests.CloudflareSession` with curl-cffi and anon_requests support
