"""HTTP transport layer with injectable transport for offline testing."""

import json as _json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Protocol


class HttpResponse:
    """A minimal HTTP response wrapper."""

    def __init__(
        self, status: int, body: bytes, headers: dict[str, str] | None = None
    ):
        self.status = status
        self.body = body
        self._headers = {k.lower(): v for k, v in (headers or {}).items()}

    def header(self, name: str) -> str | None:
        """Return a header value (case-insensitive)."""
        return self._headers.get(name.lower())

    def json(self) -> Any:
        """Parse the body as JSON."""
        return _json.loads(self.body)

    @property
    def text(self) -> str:
        """Decode the body as UTF-8."""
        return self.body.decode("utf-8", errors="replace")


class Transport(Protocol):
    """HTTP transport protocol — implement for testing or real I/O."""

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        cookies: dict[str, str] | None = None,
        timeout: float = 10.0,
    ) -> HttpResponse: ...


def _build_cookie_header(cookies: dict[str, str] | None) -> str:
    if not cookies:
        return ""
    return "; ".join(f"{k}={v}" for k, v in cookies.items())


def _merge_headers(raw: Any) -> dict[str, str]:
    """Merge HTTP headers into a dict, joining duplicates with '; '.

    urllib returns multiple ``Set-Cookie`` headers as separate tuples;
    a plain dict comprehension would silently drop all but the last.
    """
    merged: dict[str, str] = {}
    for k, v in raw:
        kl = k.lower()
        if kl in merged:
            merged[kl] += "; " + v
        else:
            merged[kl] = v
    return merged


class UrllibTransport:
    """Production transport backed by ``urllib.request``."""

    def __init__(self, timeout: float = 10.0, user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"):
        self.timeout = timeout
        self.user_agent = user_agent

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        cookies: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponse:
        # Append query parameters.
        if params:
            query = urllib.parse.urlencode(params)
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}{query}"

        req_headers = {"User-Agent": self.user_agent}
        if headers:
            req_headers.update(headers)
        cookie_str = _build_cookie_header(cookies)
        if cookie_str:
            req_headers["Cookie"] = cookie_str

        req = urllib.request.Request(url, method=method, headers=req_headers)
        try:
            with urllib.request.urlopen(
                req, timeout=timeout or self.timeout
            ) as resp:
                body = resp.read()
                resp_headers = _merge_headers(resp.getheaders())
                return HttpResponse(resp.status, body, resp_headers)
        except urllib.error.HTTPError as e:
            body = e.read()
            resp_headers = _merge_headers(e.headers.items())
            return HttpResponse(e.code, body, resp_headers)
        except urllib.error.URLError as e:
            from vtt2txt.errors import NetworkError

            raise NetworkError(f"网络请求失败: {e.reason}") from e
        except TimeoutError as e:
            from vtt2txt.errors import NetworkError

            raise NetworkError(f"请求超时: {e}") from e


_default: Transport | None = None


def default_transport() -> Transport:
    """Return the lazily-created default transport."""
    global _default
    if _default is None:
        _default = UrllibTransport()
    return _default


def set_default_transport(t: Transport | None) -> None:
    """Override the default transport (primarily for tests)."""
    global _default
    _default = t
