"""pyliveatc — Python client for LiveATC.net ATC audio feeds."""
from .version import __version__
from .models import ArchiveFile, Feed, Frequency, TopFeed
from .transport import Transport, default_transport, reset_default_transport, set_delay
from .scraper import (
    FEED_TYPES,
    fetch_feedindex,
    fetch_topfeeds,
    get_stream_url,
    iter_all_feeds,
    iter_feedindex,
    parse_feedindex_html,
    parse_search_html,
    parse_topfeeds_html,
    search,
)
from .archive import (
    ARCHIVE_TIME_SLOTS,
    build_archive_url,
    download_archive_file,
    download_range,
    fetch_archive_listing,
    list_archive_facilities,
    parse_archive_html,
)
from .dataset import (
    export_all,
    export_archives_jsonl,
    export_feeds_jsonl,
    export_topfeeds_jsonl,
)

__all__ = [
    "__version__",
    # models
    "ArchiveFile", "Feed", "Frequency", "TopFeed",
    # transport
    "Transport", "default_transport", "reset_default_transport", "set_delay",
    # scraper
    "FEED_TYPES",
    "fetch_feedindex", "fetch_topfeeds", "get_stream_url", "iter_all_feeds",
    "iter_feedindex", "parse_feedindex_html", "parse_search_html",
    "parse_topfeeds_html", "search",
    # archive
    "ARCHIVE_TIME_SLOTS",
    "build_archive_url", "download_archive_file", "download_range",
    "fetch_archive_listing", "list_archive_facilities", "parse_archive_html",
    # dataset
    "export_all", "export_archives_jsonl", "export_feeds_jsonl",
    "export_topfeeds_jsonl",
]
