"""HTTP transport for pyliveatc.

LiveATC.net is Cloudflare-protected. Use FlareSolverr for full access:

  PYLIVEATC_MODE=flaresolverr PYLIVEATC_FLARESOLVERR=http://host:8191 python ...

Environment variables (prefix PYLIVEATC_):
  PYLIVEATC_MODE        : "flaresolverr" (recommended) | "curl_cffi" | "requests" | "wayback"
  PYLIVEATC_FLARESOLVERR: FlareSolverr base URL, e.g. http://192.168.1.116:8191
                          (do NOT include /v1 — appended automatically by unblock_requests)
  PYLIVEATC_ANON        : "1" to enable IP rotation via anon_requests
  PYLIVEATC_DELAY       : float seconds between requests (default 1.5)

Access notes:
  - Scraping (search, feedindex, topfeeds): works via flaresolverr or wayback.
  - Live streams (d.liveatc.net): require a valid cf_clearance cookie from
    www.liveatc.net — FlareSolverr solves this; use get_stream_url() then
    stream_bytes() with the returned session/cookies.
  - Archive downloads: LiveATC now issues short-lived signed URLs via a
    Turnstile-protected form (archive-response.php). Direct CDN links are
    rejected with "Link Required". Automation requires a full browser session
    that can solve the Turnstile widget and submit the archive form.
"""
import os
import time
from typing import Optional

BASE_URL = "https://www.liveatc.net"
ARCHIVE_BASE = "https://archive.liveatc.net"
STREAM_BASE = "https://d.liveatc.net"

_ENV = "PYLIVEATC_"
_DEFAULT_DELAY = float(os.environ.get(f"{_ENV}DELAY", "1.5"))

_last_request: float = 0.0
_min_delay: float = _DEFAULT_DELAY
_default_transport: Optional["Transport"] = None


def _strip_v1(url: str) -> str:
    """Normalise FlareSolverr URL — strip trailing /v1 if present.

    unblock_requests appends /v1 itself; passing it twice causes 404.
    """
    return url.rstrip("/").removesuffix("/v1")


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
        raw_fs = flaresolverr_url or os.environ.get(f"{_ENV}FLARESOLVERR", "http://localhost:8191")
        self._flaresolverr_url = _strip_v1(raw_fs)
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
                                     flaresolverr_url=self._flaresolverr_url,
                                     flaresolverr_timeout_ms=120_000)

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

    def get_cf_cookies(self) -> dict:
        """Return Cloudflare clearance cookies from the current session.

        With FlareSolverr mode the session already holds cf_clearance after
        the first request.  In other modes this returns an empty dict.
        """
        try:
            jar = self.session.cookies
            return {c.name: c.value for c in jar} if hasattr(jar, "__iter__") else {}
        except Exception:
            return {}

    def stream_bytes(self, url: str, nbytes: int = 65536, **kwargs) -> bytes:
        """Read ``nbytes`` from a streaming URL (e.g. a live Icecast stream).

        Uses curl_cffi (Chrome impersonation) which bypasses Cloudflare natively
        on d.liveatc.net.  Falls back to the configured session if curl_cffi is
        unavailable.
        """
        try:
            from curl_cffi.requests import Session as CurlSession
            _throttle()
            with CurlSession(impersonate="chrome") as cs:
                r = cs.get(url, stream=True, **kwargs)
                r.raise_for_status()
                chunks = []
                got = 0
                for chunk in r.iter_content(chunk_size=min(nbytes, 8192)):
                    chunks.append(chunk)
                    got += len(chunk)
                    if got >= nbytes:
                        break
                r.close()
                return b"".join(chunks)[:nbytes]
        except ImportError:
            pass
        _throttle()
        r = self.session.get(url, stream=True, **kwargs)
        r.raise_for_status()
        chunks = []
        got = 0
        for chunk in r.iter_content(chunk_size=min(nbytes, 8192)):
            chunks.append(chunk)
            got += len(chunk)
            if got >= nbytes:
                break
        r.close()
        return b"".join(chunks)[:nbytes]

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
