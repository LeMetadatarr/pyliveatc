from pyliveatc.archive import build_archive_url, list_archive_facilities, parse_archive_html
from bs4 import BeautifulSoup


def test_parse_archive_html(archive_html):
    files = parse_archive_html(archive_html, "kjfk_app")
    assert len(files) == 4
    filenames = [af.filename for af in files]
    assert "kjfk_app-20260609-0000Z.mp3" in filenames
    assert "kjfk_app-20260609-0030Z.mp3" in filenames
    first = next(af for af in files if af.filename == "kjfk_app-20260609-0000Z.mp3")
    assert first.date == "20260609"
    assert first.time == "0000Z"
    assert first.url == "https://archive.liveatc.net/kjfk_app/kjfk_app-20260609-0000Z.mp3"


def test_build_archive_url():
    url = build_archive_url("kjfk_app", "20260609", "1200")
    assert url == "https://archive.liveatc.net/kjfk_app/kjfk_app-20260609-1200Z.mp3"

    url_z = build_archive_url("kjfk_app", "20260609", "1200Z")
    assert url_z == url


# ---------------------------------------------------------------------------
# Regression / documentation tests against a real recorded /archive.php
# response — fixture recorded via the Wayback Machine (raw, unrewritten
# snapshot) from https://www.liveatc.net/archive.php?m=kjfk_gnd,
# snapshot 2026-07-21T02:11:11Z.
# ---------------------------------------------------------------------------

def test_parse_archive_html_live_yields_no_direct_mp3_links(archive_kjfk_gnd_live_html):
    """Documents the live site's current archive access model.

    As of this snapshot, /archive.php no longer embeds direct MP3
    filenames as <option> values or <a href> links (the format
    parse_archive_html was written for) — it now only exposes a
    facility/time <select> form that POSTs through a Turnstile-protected
    flow (see the module docstring). parse_archive_html correctly returns
    an empty list rather than raising or fabricating URLs; this test
    pins that behavior against a real page so a future site-format change
    is caught explicitly instead of silently mis-parsing.
    """
    files = parse_archive_html(archive_kjfk_gnd_live_html, "kjfk_gnd")
    assert files == []


def test_list_archive_facilities_live(archive_kjfk_gnd_live_html):
    """The facility <select> on /archive.php is still scrapeable and large
    (thousands of feeds with recorded archive audio)."""
    soup = BeautifulSoup(archive_kjfk_gnd_live_html, "lxml")
    # list_archive_facilities() fetches via transport; exercise the same
    # parsing logic directly against the recorded page body.
    selects = soup.find_all("select")
    assert selects
    fac_sel = selects[0]
    facilities = [
        {"display_name": o.get_text(strip=True), "facility_key": o.get("value", "")}
        for o in fac_sel.find_all("option")
    ]
    assert len(facilities) > 3000
    assert facilities[0]["facility_key"]
    assert all(f["facility_key"] for f in facilities[:50])


def test_list_archive_facilities_uses_transport(archive_kjfk_gnd_live_html):
    class _StubTransport:
        def get_text(self, path, params=None, **kwargs):
            assert path == "/archive.php"
            return archive_kjfk_gnd_live_html

    facilities = list_archive_facilities(transport=_StubTransport())
    assert len(facilities) > 3000
    assert facilities[0]["display_name"]


def test_list_archive_facilities_empty_page():
    class _StubTransport:
        def get_text(self, path, params=None, **kwargs):
            return "<html><body>no form here</body></html>"

    assert list_archive_facilities(transport=_StubTransport()) == []
