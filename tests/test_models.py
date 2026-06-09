from pyliveatc.models import ArchiveFile, Feed, Frequency, TopFeed


def test_frequency_roundtrip():
    f = Frequency(title="Tower", frequency="119.100")
    assert Frequency.from_dict(f.to_dict()) == f


def test_feed_properties():
    f = Feed(
        mount_id="kjfk_app",
        title="KJFK - JFK App/Dep",
        up=True,
        frequencies=(Frequency("Approach", "123.900"),),
        icao="KJFK",
    )
    assert f.stream_url == "http://d.liveatc.net/kjfk_app"
    assert "archive.php?m=kjfk_app" in f.archive_url
    d = f.to_dict()
    assert d["mount_id"] == "kjfk_app"
    assert d["up"] is True
    assert len(d["frequencies"]) == 1
    assert Feed.from_dict(d) == f


def test_topfeed_to_feed():
    tf = TopFeed(rank=1, mount_id="kjfk_app", title="KJFK", listener_count=342,
                 up=True, frequencies=(), icao="KJFK")
    feed = tf.to_feed()
    assert feed.mount_id == "kjfk_app"
    assert feed.up is True


def test_archive_file_roundtrip():
    af = ArchiveFile(
        mount_id="kjfk_app",
        filename="kjfk_app-20260609-0000Z.mp3",
        date="20260609",
        time="0000Z",
        url="https://archive.liveatc.net/kjfk_app/kjfk_app-20260609-0000Z.mp3",
    )
    assert ArchiveFile.from_dict(af.to_dict()) == af
