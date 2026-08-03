"""HTML scrapers for liveatc.net pages."""
import re
from typing import Iterator, List, Optional

from bs4 import BeautifulSoup

from .models import Feed, Frequency, TopFeed
from .transport import Transport, default_transport

FEED_TYPES = [
    "all",
    "class-b",
    "class-d",
    "us-artcc",
    "international-eu",
    "international-as",
    "hf",
    "canada",
]

_MOUNT_RE = re.compile(r"/archive\.php\?m=([a-zA-Z0-9_]+)")
_ICAO_RE = re.compile(r"^([a-zA-Z]{4})", re.IGNORECASE)


def _icao_from_mount(mount_id: str) -> str:
    m = _ICAO_RE.match(mount_id)
    return m.group(1).upper() if m else ""


def _parse_freq_table(table) -> tuple:
    rows = table.find_all("tr")[1:]  # skip header
    freqs = []
    for row in rows:
        cols = row.find_all("td")
        if len(cols) >= 2:
            freqs.append(Frequency(title=cols[0].get_text(strip=True),
                                   frequency=cols[1].get_text(strip=True)))
    return tuple(freqs)


def _extract_mount(tag) -> Optional[str]:
    link = tag.find("a", href=_MOUNT_RE)
    if not link:
        # try any href containing archive.php?m=
        link = tag.find("a", href=lambda h: h and "/archive.php?m=" in h)
    if not link:
        return None
    m = _MOUNT_RE.search(link["href"])
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Top feeds
# ---------------------------------------------------------------------------

_ONCLICK_MOUNT_RE = re.compile(r"myHTML5Popup\('([^']+)'")


def _extract_topfeed_mount(tag) -> Optional[str]:
    """Extract the mount id from a topfeeds row.

    The live topfeeds.php page (as of 2026) does not link to archive.php
    from the ranking table — it embeds the mount id as the first argument
    of the ``onclick="myHTML5Popup('mount_id','icao')"`` handler on the
    "Tune In" play button. Older/alternate page layouts linked directly to
    ``archive.php?m=...``, so that form is tried first for back-compat.
    """
    mount_id = _extract_mount(tag)
    if mount_id:
        return mount_id
    link = tag.find("a", onclick=_ONCLICK_MOUNT_RE)
    if not link:
        return None
    m = _ONCLICK_MOUNT_RE.search(link["onclick"])
    return m.group(1) if m else None


def parse_topfeeds_html(html: str) -> List[TopFeed]:
    """Parse /topfeeds.php → list of TopFeed (ranked by listeners)."""
    soup = BeautifulSoup(html, "lxml")
    results = []

    # Top feeds page uses a table with rows: rank | listeners | title/link | ...
    table = soup.find("table", class_="topTable")
    tables = [table] if table is not None else soup.find_all("table")
    for tbl in tables:
        rows = tbl.find_all("tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 3:
                continue

            # Attempt to identify rank column (numeric)
            rank_text = cols[0].get_text(strip=True)
            if not rank_text.isdigit():
                continue

            rank = int(rank_text)
            listeners_text = cols[1].get_text(strip=True).replace(",", "")
            title_col = cols[2]
            title = title_col.get_text(strip=True)

            if not listeners_text.isdigit():
                # Older layout: listeners/title columns are swapped.
                listeners_text, title_col = cols[2].get_text(strip=True).replace(",", ""), cols[1]
                title = title_col.get_text(strip=True)

            mount_id = _extract_topfeed_mount(title_col) or _extract_topfeed_mount(row)
            if not mount_id:
                continue

            try:
                listener_count = int(listeners_text)
            except ValueError:
                listener_count = 0

            # Status — look for UP/DOWN text (older layout only; the live
            # page carries no per-row status, so default to up).
            up = True
            for col in cols[3:]:
                txt = col.get_text(strip=True).upper()
                if txt in ("UP", "DOWN"):
                    up = txt == "UP"
                    break

            results.append(TopFeed(
                rank=rank,
                mount_id=mount_id,
                title=title,
                listener_count=listener_count,
                up=up,
                frequencies=(),
                icao=_icao_from_mount(mount_id),
            ))

    return sorted(results, key=lambda f: f.rank)


def fetch_topfeeds(transport: Optional[Transport] = None) -> List[TopFeed]:
    t = transport or default_transport()
    html = t.get_text("/topfeeds.php")
    return parse_topfeeds_html(html)


# ---------------------------------------------------------------------------
# Search by ICAO
# ---------------------------------------------------------------------------

def parse_search_html(html: str) -> List[Feed]:
    """Parse /search/?icao=XXXX → list of Feed."""
    soup = BeautifulSoup(html, "lxml")
    stations = soup.find_all("table", class_="body")
    freq_tables = soup.find_all("table", class_="freqTable")

    results = []
    freq_idx = 0
    for station in stations:
        strong = station.find("strong")
        if not strong:
            continue
        title = strong.get_text(strip=True)

        mount_id = _extract_mount(station)
        if not mount_id:
            continue

        font = station.find("font")
        up = font.get_text(strip=True).upper() == "UP" if font else False

        freqs = ()
        if freq_idx < len(freq_tables):
            freqs = _parse_freq_table(freq_tables[freq_idx])
        freq_idx += 1

        results.append(Feed(
            mount_id=mount_id,
            title=title,
            up=up,
            frequencies=freqs,
            icao=_icao_from_mount(mount_id),
        ))

    return results


def search(icao: str, transport: Optional[Transport] = None) -> List[Feed]:
    t = transport or default_transport()
    html = t.get_text("/search/", params={"icao": icao.upper()})
    return parse_search_html(html)


# ---------------------------------------------------------------------------
# Feed index
# ---------------------------------------------------------------------------

def parse_feedindex_html(html: str) -> List[Feed]:
    """Parse /feedindex.php?type=... → list of Feed."""
    soup = BeautifulSoup(html, "lxml")
    stations = soup.find_all("table", class_="body")
    freq_tables = soup.find_all("table", class_="freqTable")

    results = []
    freq_idx = 0
    for station in stations:
        strong = station.find("strong")
        if not strong:
            continue
        title = strong.get_text(strip=True)

        mount_id = _extract_mount(station)
        if not mount_id:
            continue

        font = station.find("font")
        up = font.get_text(strip=True).upper() == "UP" if font else False

        freqs = ()
        if freq_idx < len(freq_tables):
            freqs = _parse_freq_table(freq_tables[freq_idx])
        freq_idx += 1

        results.append(Feed(
            mount_id=mount_id,
            title=title,
            up=up,
            frequencies=freqs,
            icao=_icao_from_mount(mount_id),
        ))

    return results


def fetch_feedindex(feed_type: str = "all",
                    transport: Optional[Transport] = None) -> List[Feed]:
    t = transport or default_transport()
    html = t.get_text("/feedindex.php", params={"type": feed_type})
    return parse_feedindex_html(html)


def iter_feedindex(feed_type: str = "all",
                   transport: Optional[Transport] = None) -> Iterator[Feed]:
    """Yield all feeds for the given type. Alias for fetch_feedindex for API symmetry."""
    yield from fetch_feedindex(feed_type=feed_type, transport=transport)


_AUDIO_SRC_RE = re.compile(r'<audio[^>]+src="(https?://[^"]+liveatc\.net/[^"?]+)', re.IGNORECASE)


def get_stream_url(mount_id: str, icao: str = "",
                   transport: Optional[Transport] = None) -> Optional[str]:
    """Return the authenticated live stream URL for a mount point.

    LiveATC embeds the real server URL (e.g. ``https://s1-fmt2.liveatc.net/kjfk9_s``)
    inside the ``hlisten.php`` popup player page.  The URL works only when the
    request carries valid Cloudflare clearance cookies — i.e. when the same
    session already solved the CF challenge on ``www.liveatc.net``.

    Returns the stream URL string, or None if the page was unreachable / unparseable.
    """
    t = transport or default_transport()
    try:
        html = t.get_text("/hlisten.php", params={"mount": mount_id, "icao": icao or mount_id[:4]})
    except Exception:
        return None
    m = _AUDIO_SRC_RE.search(html)
    if m:
        return m.group(1)
    return None


def iter_all_feeds(transport: Optional[Transport] = None) -> Iterator[Feed]:
    """Yield every feed across all known feed types (deduped by mount_id)."""
    seen = set()
    for feed_type in FEED_TYPES:
        try:
            for feed in fetch_feedindex(feed_type, transport=transport):
                if feed.mount_id not in seen:
                    seen.add(feed.mount_id)
                    yield feed
        except Exception:
            continue
