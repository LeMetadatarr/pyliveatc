import pytest
from pyliveatc.scraper import parse_search_html, parse_topfeeds_html, parse_feedindex_html


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
