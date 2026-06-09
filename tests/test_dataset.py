import json
import tempfile
from pathlib import Path

from pyliveatc.dataset import export_feeds_jsonl, export_archives_jsonl, export_topfeeds_jsonl
from pyliveatc.models import ArchiveFile, Feed, Frequency, TopFeed


def _make_feeds():
    return [
        Feed("kjfk_app", "KJFK App", True, (Frequency("Approach", "123.9"),), "KJFK"),
        Feed("klax_twr", "KLAX Tower", False, (Frequency("Tower", "133.9"),), "KLAX"),
    ]


def test_export_feeds_jsonl():
    feeds = _make_feeds()
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as f:
        path = f.name

    n = export_feeds_jsonl(feeds, path)
    assert n == 2
    lines = Path(path).read_text().strip().splitlines()
    assert len(lines) == 2
    row = json.loads(lines[0])
    assert row["mount_id"] == "kjfk_app"
    assert row["up"] is True
    assert len(row["frequencies"]) == 1


def test_export_archives_jsonl():
    files = [
        ArchiveFile("kjfk_app", "kjfk_app-20260609-0000Z.mp3", "20260609", "0000Z",
                    "https://archive.liveatc.net/kjfk_app/kjfk_app-20260609-0000Z.mp3"),
    ]
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = f.name
    n = export_archives_jsonl(files, path)
    assert n == 1
    row = json.loads(Path(path).read_text().strip())
    assert row["mount_id"] == "kjfk_app"
    assert row["date"] == "20260609"


def test_export_topfeeds_jsonl():
    topfeeds = [TopFeed(1, "kjfk_app", "KJFK", 342, True, (), "KJFK")]
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = f.name
    n = export_topfeeds_jsonl(topfeeds, path)
    assert n == 1
    row = json.loads(Path(path).read_text().strip())
    assert row["rank"] == 1
    assert row["listener_count"] == 342
