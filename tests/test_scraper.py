import pytest
from pyliveatc.scraper import (
    get_stream_url,
    parse_feedindex_html,
    parse_search_html,
    parse_topfeeds_html,
)


def test_parse_search_kjfk(search_kjfk_html):
    feeds = parse_search_html(search_kjfk_html)
    assert len(feeds) == 3

    app = next(f for f in feeds if f.mount_id == "kjfk_app")
    assert app.up is True
    assert "JFK" in app.title
    assert app.icao == "KJFK"
    assert app.stream_url == "http://d.liveatc.net/kjfk_app"
    assert len(app.frequencies) == 2
    freqs = {f.title: f.frequency for f in app.frequencies}
    assert freqs["Approach"] == "123.900"
    assert freqs["Departure"] == "135.900"

    gnd = next(f for f in feeds if f.mount_id == "kjfk_gnd_twr")
    assert gnd.up is True
    gnd_freqs = {f.title: f.frequency for f in gnd.frequencies}
    assert gnd_freqs["Ground"] == "121.900"

    atis = next(f for f in feeds if f.mount_id == "kjfk_atis")
    assert atis.up is False


def test_parse_topfeeds(topfeeds_html):
    feeds = parse_topfeeds_html(topfeeds_html)
    assert len(feeds) == 3
    assert feeds[0].rank == 1
    assert feeds[0].mount_id == "kjfk_app"
    assert feeds[0].listener_count == 342
    assert feeds[0].up is True
    assert feeds[1].rank == 2
    assert feeds[1].mount_id == "klax_south_tower"
    assert feeds[2].up is False


def test_parse_feedindex_same_as_search(search_kjfk_html):
    # feedindex uses same HTML structure as search
    from pyliveatc.scraper import parse_feedindex_html
    feeds = parse_feedindex_html(search_kjfk_html)
    assert len(feeds) == 3
    assert any(f.mount_id == "kjfk_gnd_twr" for f in feeds)


# ---------------------------------------------------------------------------
# Regression tests against real recorded liveatc.net responses.
#
# Fixtures recorded via the Wayback Machine (raw/unrewritten snapshots,
# `id_` suffix) — no fabricated HTML:
#   search_kjfk_live.html    <- https://www.liveatc.net/search/?icao=kjfk
#                                snapshot 2026-07-21T02:10:57Z
#   topfeeds_live.html       <- https://www.liveatc.net/topfeeds.php
#                                snapshot 2026-06-23T20:32:09Z
# ---------------------------------------------------------------------------

def test_parse_search_html_live_frequency_alignment(search_kjfk_live_html):
    """Regression for the freq-table misalignment bug.

    The real search page interleaves station rows that have no <strong>
    title (spacer rows) among the real feed rows. Indexing freq_tables by
    the station's raw position (instead of a counter over kept feeds)
    desynced every frequency table after the first spacer row — e.g.
    "KJFK Clearance Delivery #2" was reported with 7 frequencies borrowed
    from a later, unrelated station instead of its real single frequency.
    """
    feeds = parse_search_html(search_kjfk_live_html)
    assert len(feeds) == 34

    del2 = next(f for f in feeds if f.mount_id == "kjfk_del2")
    assert [fr.title for fr in del2.frequencies] == ["JFK Clearance Delivery"]

    arinc = next(f for f in feeds if f.mount_id == "kjfk_arinc")
    assert len(arinc.frequencies) == 2

    twr = next(f for f in feeds if f.mount_id == "kjfk_twr")
    assert twr.up is True
    assert twr.icao == "KJFK"

    # No station should inherit an implausibly large frequency table —
    # that was the observable symptom of the misalignment bug.
    assert all(len(f.frequencies) <= 7 for f in feeds)


def test_parse_topfeeds_html_live(topfeeds_live_html):
    """Regression: the live topfeeds.php page has no archive.php links at
    all — the mount id is only available via the play button's
    ``onclick="myHTML5Popup('mount_id','icao')"`` handler, and the column
    order is rank | listeners | title (not rank | title | listeners).
    The old parser returned an empty list against this real page.
    """
    feeds = parse_topfeeds_html(topfeeds_live_html)
    assert len(feeds) == 50

    top = feeds[0]
    assert top.rank == 1
    assert top.mount_id == "rjtt_control"
    assert top.listener_count == 23
    assert top.up is True
    assert "Tokyo" in top.title

    second = feeds[1]
    assert second.rank == 2
    assert second.mount_id == "ksfo_twr"

    # ranks are strictly increasing / sorted
    assert [f.rank for f in feeds] == sorted(f.rank for f in feeds)


def test_parse_topfeeds_html_legacy_format_still_works(topfeeds_html):
    """The older rank | title | listeners | status layout (hand-built
    fixture, superseded by the live one above) must keep working."""
    feeds = parse_topfeeds_html(topfeeds_html)
    assert len(feeds) == 3
    assert feeds[0].mount_id == "kjfk_app"
    assert feeds[0].listener_count == 342
    assert feeds[2].up is False


def test_get_stream_url_live(hlisten_kjfk_gnd_live_html):
    """get_stream_url() must extract the real <audio src> from hlisten.php."""

    class _StubTransport:
        def get_text(self, path, params=None, **kwargs):
            assert path == "/hlisten.php"
            assert params == {"mount": "kjfk_gnd", "icao": "kjfk"}
            return hlisten_kjfk_gnd_live_html

    url = get_stream_url("kjfk_gnd", icao="kjfk", transport=_StubTransport())
    assert url == "https://s1-bos.liveatc.net/kjfk_gnd"


def test_get_stream_url_malformed_page_returns_none():
    class _StubTransport:
        def get_text(self, path, params=None, **kwargs):
            return "<html><body>no audio tag here</body></html>"

    assert get_stream_url("kjfk_gnd", transport=_StubTransport()) is None
