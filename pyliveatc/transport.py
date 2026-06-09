"""HTTP transport for pyliveatc.

LiveATC.net is Cloudflare-protected, so we require unblock_requests'
CloudflareSession. Optionally layer anon_requests for IP rotation.

Environment variables (prefix PYLIVEATC_):
  PYLIVEATC_MODE        : "curl_cffi" (default) | "requests" | "flaresolverr" | "wayback"
  PYLIVEATC_ANON        : "1" to enable IP rotation via anon_requests
  PYLIVEATC_DELAY       : float seconds between requests (default 1.5)
  PYLIVEATC_FLARESOLVERR: flaresolverr URL when MODE=flaresolverr
"""
import os
import time
from typing import Optional

BASE_URL = "https://www.liveatc.net"
ARCHIVE_BASE = "https://archive.liveatc.net"

# Live stream base — real servers are s{N}-fmt2.liveatc.net or s{N}-{city}.liveatc.net.
# The stream URL with a nocache token is returned by hlisten.php; without it all
# stream/archive subdomains return 403 (Cloudflare-gated, requires CF clearance cookie).
STREAM_BASE = "http://d.liveatc.net"  # canonical redirect alias

_ENV = "PYLIVEATC_"
_DEFAULT_DELAY = float(os.environ.get(f"{_ENV}DELAY", "1.5"))

_last_request: float = 0.0
_min_delay: float = _DEFAULT_DELAY
_default_transport: Optional["Transport"] = None


def set_delay(seconds: float) -> None:
    global _min_delay
    _min_delay = max(0.0, seconds)


def _throttle() -> None:
    global _last_request
    now = time.monotonic()
    gap = now - _last_request
    if gap < _min_delay:
        time.sleep(_min_delay - gap)
    _last_request = time.monotonic()


class Transport:
    """Requests-compatible session wrapper with CF bypass and throttling."""

    def __init__(self, mode: Optional[str] = None, anon: bool = False,
                 flaresolverr_url: Optional[str] = None):
        self._mode = mode or os.environ.get(f"{_ENV}MODE", "curl_cffi")
        self._anon = anon or bool(os.environ.get(f"{_ENV}ANON"))
        self._flaresolverr_url = flaresolverr_url or os.environ.get(
            f"{_ENV}FLARESOLVERR", "http://localhost:8191/v1"
        )
        self._session = None

    @property
    def session(self):
        if self._session is None:
            self._session = self._make_session()
        return self._session

    def _make_session(self):
        if self._mode == "wayback":
            from unblock_requests import CloudflareSession
            return CloudflareSession(mode="wayback")

        if self._mode == "flaresolverr":
            from unblock_requests import CloudflareSession
            return CloudflareSession(mode="flaresolverr",
                                     flaresolverr_url=self._flaresolverr_url)

        try:
            from unblock_requests import CloudflareSession
            inner = CloudflareSession(mode=self._mode)
        except Exception:
            import requests
            inner = requests.Session()

        if self._anon:
            try:
                from anon_requests import RotatingProxySession, ProxyType
                return RotatingProxySession(
                    proxy_type=ProxyType.SOCKS5,
                    session_factory=lambda: inner,
                )
            except ImportError:
                pass

        return inner

    def get(self, path: str, params=None, base: str = BASE_URL, **kwargs):
        _throttle()
        url = base + path if path.startswith("/") else path
        return self.session.get(url, params=params, **kwargs)

    def get_text(self, path: str, params=None, base: str = BASE_URL, **kwargs) -> str:
        r = self.get(path, params=params, base=base, **kwargs)
        r.raise_for_status()
        return r.text

    def get_bytes(self, url: str, **kwargs) -> bytes:
        _throttle()
        r = self.session.get(url, **kwargs)
        r.raise_for_status()
        return r.content

    def close(self) -> None:
        if self._session is not None:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None


def default_transport() -> Transport:
    global _default_transport
    if _default_transport is None:
        _default_transport = Transport()
    return _default_transport


def reset_default_transport() -> None:
    global _default_transport
    if _default_transport is not None:
        _default_transport.close()
        _default_transport = None
