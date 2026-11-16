"""Unified exceptions, exit-code constants, and secret redaction."""

# Exit codes — shared across CLI and fetcher.
EXIT_OK = 0
EXIT_GENERIC = 1
EXIT_USAGE = 2
EXIT_LOGIN = 3


class BiliError(Exception):
    """Base class for all Bilibili-related errors."""


class LoginRequired(BiliError):
    """No SESSDATA available but the operation requires authentication."""


class LoginExpired(BiliError):
    """SESSDATA has expired (Bilibili code -101) or the QR code timed out."""


class NoSubtitle(BiliError):
    """The video has no subtitle tracks, or the requested language was not found."""


class VideoNotFound(BiliError):
    """The BV number does not resolve to a visible video."""


class RateLimited(BiliError):
    """Bilibili returned a rate-limit response (HTTP 412 / code -412)."""


class NetworkError(BiliError):
    """A low-level network failure (URLError, timeout, etc.)."""


def redact(secret: str, keep_head: int = 4, keep_tail: int = 4) -> str:
    """Mask a secret for safe display.

    Returns ``"***"`` when *secret* is empty or too short to meaningfully
    truncate.  Otherwise keeps the first *keep_head* and last *keep_tail*
    characters, replacing the middle with ``"***"``.
    """
    if not secret:
        return "***"
    if len(secret) <= keep_head + keep_tail + 3:
        return "***"
    return f"{secret[:keep_head]}***{secret[-keep_tail:]}"
