"""Data models for pyliveatc."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Frequency:
    title: str      # e.g. "Ground", "Tower", "ATIS", "Approach"
    frequency: str  # e.g. "121.900"

    def to_dict(self) -> dict:
        return {"title": self.title, "frequency": self.frequency}

    @staticmethod
    def from_dict(d: dict) -> "Frequency":
        return Frequency(title=d["title"], frequency=d["frequency"])


@dataclass(frozen=True)
class Feed:
    mount_id: str                          # Icecast mount point, e.g. "kjfk_app"
    title: str                             # Human label, e.g. "KJFK - JFK App/Dep"
    up: bool                               # True = stream is currently live
    frequencies: tuple = field(default_factory=tuple)  # tuple[Frequency, ...]
    icao: str = ""                         # ICAO prefix, derived when possible

    @property
    def stream_url(self) -> str:
        return f"http://d.liveatc.net/{self.mount_id}"

    @property
    def archive_url(self) -> str:
        return f"https://www.liveatc.net/archive.php?m={self.mount_id}"

    def to_dict(self) -> dict:
        return {
            "mount_id": self.mount_id,
            "title": self.title,
            "up": self.up,
            "icao": self.icao,
            "stream_url": self.stream_url,
            "archive_url": self.archive_url,
            "frequencies": [f.to_dict() for f in self.frequencies],
        }

    @staticmethod
    def from_dict(d: dict) -> "Feed":
        return Feed(
            mount_id=d["mount_id"],
            title=d["title"],
            up=d["up"],
            icao=d.get("icao", ""),
            frequencies=tuple(Frequency.from_dict(f) for f in d.get("frequencies", [])),
        )


@dataclass(frozen=True)
class TopFeed:
    rank: int
    mount_id: str
    title: str
    listener_count: int
    up: bool
    frequencies: tuple = field(default_factory=tuple)  # tuple[Frequency, ...]
    icao: str = ""

    @property
    def stream_url(self) -> str:
        return f"http://d.liveatc.net/{self.mount_id}"

    @property
    def archive_url(self) -> str:
        return f"https://www.liveatc.net/archive.php?m={self.mount_id}"

    def to_dict(self) -> dict:
        return {
            "rank": self.rank,
            "mount_id": self.mount_id,
            "title": self.title,
            "listener_count": self.listener_count,
            "up": self.up,
            "icao": self.icao,
            "stream_url": self.stream_url,
            "frequencies": [f.to_dict() for f in self.frequencies],
        }

    def to_feed(self) -> Feed:
        return Feed(
            mount_id=self.mount_id,
            title=self.title,
            up=self.up,
            frequencies=self.frequencies,
            icao=self.icao,
        )


@dataclass(frozen=True)
class ArchiveFile:
    mount_id: str
    filename: str   # e.g. "kjfk_app-20260601-1200Z.mp3"
    date: str       # "20260601"
    time: str       # "1200Z"
    url: str        # full https://archive.liveatc.net/... URL

    def to_dict(self) -> dict:
        return {
            "mount_id": self.mount_id,
            "filename": self.filename,
            "date": self.date,
            "time": self.time,
            "url": self.url,
        }

    @staticmethod
    def from_dict(d: dict) -> "ArchiveFile":
        return ArchiveFile(
            mount_id=d["mount_id"],
            filename=d["filename"],
            date=d["date"],
            time=d["time"],
            url=d["url"],
        )
