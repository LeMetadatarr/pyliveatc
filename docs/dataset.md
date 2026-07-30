# Dataset

## Configs

### `feeds`: Feed metadata catalog

One row per unique feed across all feed types.

| Field | Type | Description |
|-------|------|-------------|
| `mount_id` | str | Icecast mount point, e.g. `kjfk_app` |
| `title` | str | Human feed name |
| `icao` | str | 4-char ICAO prefix |
| `up` | bool | Live at scrape time |
| `stream_url` | str | `http://d.liveatc.net/{mount_id}` |
| `archive_url` | str | Archive listing page URL |
| `frequencies` | list[{title, frequency}] | Associated ATC frequencies |

### `topfeeds`: Top-50 by listener count

Adds `rank` (int) and `listener_count` (int) to the feeds schema.

### `archives`: Archive file inventory

One row per 30-minute MP3 segment (requires per-mount archive scraping).

| Field | Type | Description |
|-------|------|-------------|
| `mount_id` | str | |
| `filename` | str | `{mount_id}-{YYYYMMDD}-{HHMM}Z.mp3` |
| `date` | str | `YYYYMMDD` |
| `time` | str | `HHMMZ` |
| `url` | str | Direct CDN URL |

## ML suitability

- **Feed catalog**: maps airport code to frequency to ATC function. Use it for intent classification, for example "what frequency is JFK tower?"
- **Archive audio**: 30-minute MP3 segments of real ATC radio. Use it for ASR fine-tuning, speaker diarization, radio-domain language modeling, and noise-robustness training.
- **Listener counts**: a proxy for airport busyness. Use it as a feature for traffic-prediction models.

## Export

```python
from pyliveatc.dataset import export_all

counts = export_all(
    out_dir="./liveatc_data",
    feed_types=["class-b", "international-eu"],
)
# writes: feeds_class_b.jsonl, feeds_international_eu.jsonl,
#         feeds_all.jsonl, topfeeds.jsonl, manifest.json
```

---
[← Architecture](architecture.md) · [Home](README.md) · [CLI →](cli.md)
