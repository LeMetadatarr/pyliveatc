"""Archive listing and download helpers for liveatc.net.

The /archive.php page has two <select> elements:
  1. facility — human-readable names (e.g. "KJFK Gnd/Twr"), value is a
     facility key (e.g. "KJFK-GndTwr") — NOT the Icecast mount_id.
  2. time — "HHMM-HHMMZ" slot options for the current UTC date.

Submitting the form POSTs to /archive.php which redirects to a CDN URL:
  https://archive.liveatc.net/{mount_id}/{mount_id}-YYYYMMDD-HHMMZ.mp3

Since we know the mount_id and want specific dates/times, we construct
archive URLs directly using the well-known pattern rather than scraping
the form — no form POST needed.
"""
import re
from pathlib import Path
from typing import List, Optional

from bs4 import BeautifulSoup

from .models import ArchiveFile
from .transport import ARCHIVE_BASE, Transport, default_transport

_ARCHIVE_FILE_RE = re.compile(
    r"([a-zA-Z0-9_]+)-(\d{8})-(\d{4}Z)\.mp3", re.IGNORECASE
)

# Time slots available on the archive page (48 per day)
ARCHIVE_TIME_SLOTS = [
    f"{h:02d}{m:02d}Z"
    for h in range(24)
    for m in (0, 30)
]


def parse_archive_html(html: str, mount_id: str) -> List[ArchiveFile]:
    """Parse /archive.php?m={mount_id} → list of ArchiveFile.

    Constructs CDN URLs directly from the time-slot select options,
    since the form itself requires POST + redirect to resolve the file.
    """
    soup = BeautifulSoup(html, "lxml")
    results = []

    # Try direct MP3 option values first (older page format)
    for option in soup.find_all("option"):
        value = option.get("value", "")
        m = _ARCHIVE_FILE_RE.search(value)
        if m:
            mid, date, time_ = m.group(1), m.group(2), m.group(3)
            filename = f"{mid}-{date}-{time_}.mp3"
            url = f"{ARCHIVE_BASE}/{mid}/{filename}"
            results.append(ArchiveFile(
                mount_id=mid,
                filename=filename,
                date=date,
                time=time_,
                url=url,
            ))

    # Also check direct links
    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = _ARCHIVE_FILE_RE.search(href)
        if m and "archive.liveatc.net" in href:
            mid, date, time_ = m.group(1), m.group(2), m.group(3)
            filename = f"{mid}-{date}-{time_}.mp3"
            results.append(ArchiveFile(
                mount_id=mid,
                filename=filename,
                date=date,
                time=time_,
                url=href,
            ))

    # Deduplicate by filename
    seen = set()
    deduped = []
    for af in results:
        if af.filename not in seen:
            seen.add(af.filename)
            deduped.append(af)

    return deduped


def fetch_archive_listing(mount_id: str,
                          transport: Optional[Transport] = None) -> List[ArchiveFile]:
    """Return available archive files for a mount point."""
    t = transport or default_transport()
    html = t.get_text("/archive.php", params={"m": mount_id})
    return parse_archive_html(html, mount_id)


def list_archive_facilities(transport: Optional[Transport] = None) -> List[dict]:
    """Return all feeds that have archive files available.

    Parses the facility <select> on /archive.php, which lists every feed
    that has audio in the archive (3,400+ entries).

    Returns list of dicts with keys: display_name, facility_key
    """
    t = transport or default_transport()
    html = t.get_text("/archive.php")
    soup = BeautifulSoup(html, "lxml")
    selects = soup.find_all("select")
    if not selects:
        return []
    fac_sel = selects[0]
    return [
        {"display_name": o.get_text(strip=True), "facility_key": o.get("value", "")}
        for o in fac_sel.find_all("option")
    ]


def build_archive_url(mount_id: str, date: str, time_z: str) -> str:
    """Construct an archive MP3 URL directly.

    Args:
        mount_id: e.g. "kjfk_app"
        date: "YYYYMMDD"
        time_z: "HHMM" or "HHMMZ" — Z appended if missing
    """
    if not time_z.endswith("Z"):
        time_z = time_z + "Z"
    filename = f"{mount_id}-{date}-{time_z}.mp3"
    return f"{ARCHIVE_BASE}/{mount_id}/{filename}"


def download_archive_file(archive_file: ArchiveFile,
                          dest_dir: str,
                          transport: Optional[Transport] = None) -> Path:
    """Download a single archive MP3. Returns the local path."""
    t = transport or default_transport()
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    out_path = dest / archive_file.filename
    data = t.get_bytes(archive_file.url)
    out_path.write_bytes(data)
    return out_path


def stream_live(mount_id: str, dest_path: str, seconds: int = 30,
                transport: Optional[Transport] = None) -> int:
    """Record ``seconds`` of live audio from a mount point to an MP3 file.

    Uses curl_cffi (Chrome impersonation) for the actual stream connection —
    d.liveatc.net is Cloudflare-protected but curl_cffi bypasses it natively
    without needing a FlareSolverr session.  Falls back to the provided
    transport session if curl_cffi is unavailable.

    Returns number of bytes written.
    """
    import time as _time
    url = f"https://d.liveatc.net/{mount_id}"
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        from curl_cffi.requests import Session as CurlSession
        session = CurlSession(impersonate="chrome")
        r = session.get(url, stream=True)
        r.raise_for_status()
        total = 0
        deadline = _time.monotonic() + seconds
        with open(dest, "wb") as fh:
            for chunk in r.iter_content(chunk_size=4096):
                if not chunk:
                    continue
                fh.write(chunk)
                total += len(chunk)
                if _time.monotonic() >= deadline:
                    break
        r.close()
        return total
    except ImportError:
        pass

    # Fallback: use the provided transport session
    t = transport or default_transport()
    r = t.session.get(url, stream=True)
    r.raise_for_status()
    total = 0
    deadline = _time.monotonic() + seconds
    with open(dest, "wb") as fh:
        for chunk in r.iter_content(chunk_size=4096):
            if not chunk:
                continue
            fh.write(chunk)
            total += len(chunk)
            if _time.monotonic() >= deadline:
                break
    r.close()
    return total


def download_range(mount_id: str,
                   date: str,
                   hours: List[int],
                   dest_dir: str,
                   transport: Optional[Transport] = None) -> List[Path]:
    """Download specific hours (UTC) of archive audio for a mount point.

    Args:
        mount_id: e.g. "kjfk_app"
        date: "YYYYMMDD"
        hours: list of UTC hours, e.g. [12, 13, 14]
        dest_dir: local directory to save MP3 files

    Each hour produces two 30-minute files (HH00Z and HH30Z).
    Returns list of successfully downloaded paths.
    """
    t = transport or default_transport()
    paths = []
    for hour in hours:
        for minute in (0, 30):
            time_z = f"{hour:02d}{minute:02d}Z"
            url = build_archive_url(mount_id, date, time_z)
            filename = f"{mount_id}-{date}-{time_z}.mp3"
            af = ArchiveFile(mount_id=mount_id, filename=filename,
                             date=date, time=time_z, url=url)
            try:
                path = download_archive_file(af, dest_dir, transport=t)
                paths.append(path)
            except Exception:
                pass
    return paths
