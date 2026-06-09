# AGENTS.md — pyliveatc

Python client library for LiveATC.net — live and archived ATC audio feed discovery and download.

## Setup

```bash
pip install -e ".[stealth,test]"
```

## Test

```bash
pytest -m "not live"     # offline: models, HTML parsing, dataset — no network
pytest -m live           # live network tests (requires unblock_requests)
```

## Layout

- `pyliveatc/transport.py` — `Transport` wrapping `unblock_requests.CloudflareSession`. Env prefix `PYLIVEATC_`.
- `pyliveatc/models.py` — `Feed`, `TopFeed`, `Frequency`, `ArchiveFile` frozen dataclasses.
- `pyliveatc/scraper.py` — HTML parsers + `search()`, `fetch_topfeeds()`, `fetch_feedindex()`, `iter_all_feeds()`.
- `pyliveatc/archive.py` — `fetch_archive_listing()`, `download_archive_file()`, `download_range()`.
- `pyliveatc/dataset.py` — JSONL export, `export_all()`.
- `tests/fixtures/` — Static HTML for offline parser tests.

## Conventions

- Branches: work on `dev`, stable on `master`; never `main`.
- Never edit `pyliveatc/version.py`; gh-automations bumps semver from commit prefixes.
- Commit identity: JarbasAi <jarbasai@mailfence.com>.
- All PRs squash-merged; always open draft PRs into `dev`.
