"""Create/update the HuggingFace dataset card and dataset_info for liveatc-atc-audio-archive.

Run once before or after a scrape to set up the repo metadata.

Usage::

    HF_TOKEN=hf_... python3 build_dataset_card.py \\
        --repo TigreGotico/liveatc-atc-audio-archive
"""
import argparse
import os
import tempfile
from pathlib import Path

CARD = """---
language:
- en
- multilingual
license: other
license_name: liveatc-personal-use
license_link: https://www.liveatc.net/
tags:
- audio
- speech
- air-traffic-control
- atc
- aviation
- asr
pretty_name: LiveATC Archive — Air Traffic Control Audio
size_categories:
- 10B<n<100B
task_categories:
- automatic-speech-recognition
- audio-classification
---

# LiveATC Archive — Air Traffic Control Audio

Archived 30-minute ATC (Air Traffic Control) audio recordings scraped from
[LiveATC.net](https://www.liveatc.net/) across 3,600+ global airport feeds.

## Dataset structure

```
data/
  {region}/
    {facility_key}/
      {facility_key}-{Mon}-{DD}-{YYYY}-{HHMM}Z.m4a
metadata.jsonl
```

**Regions:** `usa`, `canada`, `europe`, `japan_korea`, `australia`, `china`,
`asia`, `russia`, `africa`, `south_america`, `central_america`, `pacific`, `other`

Each audio file is a 30-minute M4A recording (AAC-LC, mono, ~2.5 kbps average).
File sizes range from ~130 KB (quiet/night slots) to ~2 MB (busy traffic periods).

## Metadata fields

| Field | Description |
|-------|-------------|
| `file` | Path in repo e.g. `data/usa/KJFK-Del3/...m4a` |
| `facility_key` | LiveATC facility key e.g. `KJFK-Del3` |
| `facility_label` | Human-readable label e.g. `KJFK Del Clearance 3` |
| `region` | Geographic region |
| `date` | UTC date `YYYYMMDD` |
| `time_slot` | UTC time slot `HHMMZ` |
| `bytes` | File size in bytes |
| `scraped_utc` | ISO timestamp when scraped |

## License

Audio recordings are sourced from LiveATC.net. Use is subject to
[LiveATC.net's terms of service](https://www.liveatc.net/). Intended for
research and accessibility purposes only.

## Intended use

- Automatic Speech Recognition (ASR) training/evaluation for aviation English
- Speaker diarization research
- Audio classification (airport activity levels, traffic type)
- Accessibility tools for deaf/hard-of-hearing users following ATC communications
"""

DATASET_INFO = {
    "config_name": "default",
    "features": [
        {"name": "audio", "dtype": {"audio": {"sampling_rate": 22050}}},
        {"name": "facility_key", "dtype": "string"},
        {"name": "facility_label", "dtype": "string"},
        {"name": "region", "dtype": "string"},
        {"name": "date", "dtype": "string"},
        {"name": "time_slot", "dtype": "string"},
        {"name": "bytes", "dtype": "int64"},
        {"name": "scraped_utc", "dtype": "string"},
    ],
    "splits": [{"name": "train"}],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="TigreGotico/liveatc-atc-audio-archive")
    args = ap.parse_args()

    token = os.environ.get("HF_TOKEN")
    if not token:
        raise SystemExit("Set HF_TOKEN")

    from huggingface_hub import HfApi
    import json

    api = HfApi(token=token)
    api.create_repo(repo_id=args.repo, repo_type="dataset", private=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        card_path = Path(td) / "README.md"
        card_path.write_text(CARD)
        api.upload_file(path_or_fileobj=str(card_path), path_in_repo="README.md",
                        repo_id=args.repo, repo_type="dataset",
                        commit_message="add dataset card")
        print(f"Uploaded README.md to {args.repo}")

    print(f"Dataset card set up at https://huggingface.co/datasets/{args.repo}")


if __name__ == "__main__":
    main()
