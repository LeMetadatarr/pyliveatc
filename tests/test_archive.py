from pyliveatc.archive import build_archive_url, parse_archive_html


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
