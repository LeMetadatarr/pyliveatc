"""Dataset export helpers for pyliveatc.

Configs:
  "feeds"    — one row per Feed (mount_id, title, icao, frequencies, stream_url, up)
  "archives" — one row per ArchiveFile (mount_id, date, time, url, filename)

Usage::

    from pyliveatc.dataset import export_all
    counts = export_all("./liveatc_data", feed_types=["class-b", "international-eu"])
"""
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .models import ArchiveFile, Feed, TopFeed
from .scraper import FEED_TYPES, fetch_feedindex, fetch_topfeeds
from .transport import Transport, default_transport

CONFIGS = ("feeds", "archives", "topfeeds")


# ---------------------------------------------------------------------------
# Row serialisers
# ---------------------------------------------------------------------------

def _feed_row(feed: Feed) -> dict:
    return feed.to_dict()


def _archive_row(af: ArchiveFile) -> dict:
    return af.to_dict()


def _topfeed_row(tf: TopFeed) -> dict:
    return tf.to_dict()


# ---------------------------------------------------------------------------
# JSONL writers
# ---------------------------------------------------------------------------

def export_feeds_jsonl(feeds: Iterable[Feed], path: str) -> int:
    """Write feeds to JSONL. Returns row count."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(out, "w", encoding="utf-8") as fh:
        for feed in feeds:
            fh.write(json.dumps(_feed_row(feed), ensure_ascii=False) + "\n")
            n += 1
    return n


def export_archives_jsonl(archive_files: Iterable[ArchiveFile], path: str) -> int:
    """Write archive file records to JSONL. Returns row count."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(out, "w", encoding="utf-8") as fh:
        for af in archive_files:
            fh.write(json.dumps(_archive_row(af), ensure_ascii=False) + "\n")
            n += 1
    return n


def export_topfeeds_jsonl(topfeeds: Iterable[TopFeed], path: str) -> int:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(out, "w", encoding="utf-8") as fh:
        for tf in topfeeds:
            fh.write(json.dumps(_topfeed_row(tf), ensure_ascii=False) + "\n")
            n += 1
    return n


# ---------------------------------------------------------------------------
# Full export
# ---------------------------------------------------------------------------

def export_all(out_dir: str,
               feed_types: Optional[List[str]] = None,
               transport: Optional[Transport] = None,
               include_topfeeds: bool = True) -> Dict[str, int]:
    """Crawl feed index and top feeds; write JSONL files + manifest.

    Returns dict of {filename: row_count}.
    """
    t = transport or default_transport()
    types = feed_types or FEED_TYPES
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    counts: Dict[str, int] = {}

    # Per-type feed files
    seen_mounts = set()
    all_feeds: List[Feed] = []
    for feed_type in types:
        try:
            feeds = fetch_feedindex(feed_type, transport=t)
        except Exception:
            continue
        fname = f"feeds_{feed_type.replace('-', '_')}.jsonl"
        n = export_feeds_jsonl(feeds, str(out / fname))
        counts[fname] = n
        for feed in feeds:
            if feed.mount_id not in seen_mounts:
                seen_mounts.add(feed.mount_id)
                all_feeds.append(feed)

    # Combined deduplicated feed file
    n = export_feeds_jsonl(all_feeds, str(out / "feeds_all.jsonl"))
    counts["feeds_all.jsonl"] = n

    # Top feeds
    if include_topfeeds:
        try:
            topfeeds = fetch_topfeeds(transport=t)
            n = export_topfeeds_jsonl(topfeeds, str(out / "topfeeds.jsonl"))
            counts["topfeeds.jsonl"] = n
        except Exception:
            pass

    # Manifest
    manifest = {"out_dir": str(out), "feed_types": types, "files": counts}
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False)
    )

    return counts
