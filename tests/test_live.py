"""Live network tests — require unblock_requests and a real connection.

Run with: pytest -m live
"""
import pytest

pytestmark = pytest.mark.live


def test_search_kjfk():
    from pyliveatc import search
    feeds = search("KJFK")
    assert len(feeds) > 0
    for feed in feeds:
        assert feed.mount_id
        assert feed.title
        assert isinstance(feed.up, bool)
        assert feed.stream_url.startswith("http://d.liveatc.net/")


def test_topfeeds():
    from pyliveatc import fetch_topfeeds
    feeds = fetch_topfeeds()
    assert len(feeds) > 0
    assert feeds[0].rank == 1
    assert feeds[0].listener_count >= 0


def test_fetch_feedindex_all():
    from pyliveatc import fetch_feedindex
    feeds = fetch_feedindex("all")
    assert len(feeds) > 10


def test_fetch_archive_listing():
    from pyliveatc import fetch_archive_listing
    # KJFK approach is a reliable feed
    files = fetch_archive_listing("kjfk_app")
    assert len(files) > 0
    assert all(af.url.endswith(".mp3") for af in files)
