"""QR-code login via Bilibili's Web passport API.

Flow:
  1. ``/qrcode/generate`` → ``{url, qrcode_key}``
  2. Render QR code (``qrcode`` package if installed, else print URL);
     callers may override rendering via the ``on_qrcode`` callback
  3. Poll ``/qrcode/poll`` every *poll_interval* seconds:
     - 86101 = waiting for scan
     - 86090 = scanned, awaiting confirmation
     - 86038 = QR code expired → regenerate (up to *max_refreshes*
       times within the *max_wait* budget), then ``LoginExpired``
     - 0     = success → extract SESSDATA from ``data.url`` or ``Set-Cookie``
  4. Persist SESSDATA via ``session.save_session``
"""

import sys
import time
from urllib.parse import parse_qs, urlparse

from bili_sub2txt.bilibili.net import Transport, default_transport
from bili_sub2txt.bilibili.session import save_session
from bili_sub2txt.errors import LoginExpired

GENERATE_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
POLL_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"


def render_qrcode(url: str) -> str:
    """Render *url* as a terminal QR code, or fall back to printing the URL.

    Issue #7 (P2) hardening:
      - quiet-zone ``border=4`` (ISO/IEC 18004 recommendation, was 1);
      - two module rows merged per text line via half-block characters,
        halving the QR height so it fits in typical terminals;
      - wrapped in an explicit black-on-white ANSI escape so the code
        keeps the correct polarity on dark-themed terminals (plain
        ``█`` on dark themes renders inverted and fails to scan).
    """
    try:
        import qrcode

        qr = qrcode.QRCode(border=4)
        qr.add_data(url)
        qr.make(fit=True)
        matrix = qr.get_matrix()
        # (top, bottom) module pair -> glyph; foreground = dark module.
        glyphs = {
            (True, True): "\u2588",   # █ full block
            (True, False): "\u2580",  # ▀ upper half
            (False, True): "\u2584",  # ▄ lower half
            (False, False): " ",
        }
        width = len(matrix[0])
        lines = []
        for r in range(0, len(matrix), 2):
            top = matrix[r]
            bottom = matrix[r + 1] if r + 1 < len(matrix) else [False] * width
            lines.append(
                "".join(glyphs[(bool(t), bool(b))] for t, b in zip(top, bottom))
            )
        body = "\n".join(lines)
        return f"\x1b[30;47m{body}\x1b[0m"
    except ImportError:
        return f"请用手机扫描以下链接登录:\n{url}"


def _extract_sessdata_from_url(url_str: str) -> str | None:
    """Pull ``SESSDATA`` from the query string of *url_str*."""
    if not url_str:
        return None
    params = parse_qs(urlparse(url_str).query)
    vals = params.get("SESSDATA")
    return vals[0] if vals else None


def _extract_sessdata_from_cookie_header(set_cookie: str | None) -> str | None:
    """Pull ``SESSDATA`` from a ``Set-Cookie`` header value."""
    if not set_cookie:
        return None
    for part in set_cookie.split(";"):
        part = part.strip()
        if part.startswith("SESSDATA="):
            return part[len("SESSDATA=") :]
    return None


def _show_qrcode(qr_url: str, on_qrcode=None) -> None:
    """Present *qr_url* to the user, preferring a caller-supplied callback.

    Precedence (issue #7, P1):
      1. ``on_qrcode`` callback — fully replaces terminal rendering, so
         programmatic callers (CI, pipes, GUI/agent wrappers) get the
         raw login URL;
      2. interactive TTY — terminal block QR code;
      3. non-TTY stdout — print the login URL to stderr instead of an
         unusable block code.
    """
    if on_qrcode is not None:
        on_qrcode(qr_url)
        return
    if sys.stdout.isatty():
        print(render_qrcode(qr_url))
    else:
        print(f"检测到非交互终端,请用手机打开以下链接登录:\n{qr_url}", file=sys.stderr)


def _generate_qrcode(t: Transport) -> tuple[str, str]:
    """Call ``/qrcode/generate`` and return ``(qr_url, qrcode_key)``."""
    resp = t.request("GET", GENERATE_URL)
    data = resp.json()
    if data.get("code") != 0:
        raise LoginExpired(
            f"二维码生成失败: {data.get('message', '')}"
        )
    return data["data"]["url"], data["data"]["qrcode_key"]


def login(
    transport: Transport | None = None,
    *,
    on_status=None,
    on_qrcode=None,
    poll_interval: float = 2.0,
    max_wait: float = 180.0,
    max_refreshes: int = 2,
    _sleep=time.sleep,
) -> str:
    """Perform QR-code login and persist the session.

    Args:
        transport: HTTP transport; defaults to ``default_transport()``.
        on_status: optional ``callable(poll_code, poll_data)`` invoked on
            every poll response.
        on_qrcode: optional ``callable(qr_url)`` invoked whenever a QR code
            is (re)generated; when provided it replaces the default
            terminal rendering.
        poll_interval: seconds between polls.
        max_wait: overall login budget in seconds (shared across QR-code
            refreshes, not per code).
        max_refreshes: how many times an expired QR code (poll code 86038)
            is regenerated before giving up; ``0`` restores the legacy
            fail-immediately behaviour.
        _sleep: sleep function (injectable for tests).

    Returns the ``SESSDATA`` string on success.  Raises ``LoginExpired``
    on timeout or QR-code expiry.
    """
    t = transport or default_transport()

    # Step 1: generate QR code.
    qr_url, qrcode_key = _generate_qrcode(t)
    _show_qrcode(qr_url, on_qrcode)
    print("\n请使用 B 站手机客户端扫描上方二维码登录。", file=sys.stderr)

    # Step 2: poll until success, expiry, or timeout.
    elapsed = 0.0
    refreshes = 0
    while elapsed < max_wait:
        resp = t.request("GET", POLL_URL, params={"qrcode_key": qrcode_key})
        data = resp.json()
        poll_data = data.get("data") or {}
        poll_code = poll_data.get("code", 0)

        if on_status:
            on_status(poll_code, poll_data)

        if poll_code == 0:
            # Success — try data.url first, then Set-Cookie header.
            data_url = poll_data.get("url", "")
            sessdata = _extract_sessdata_from_url(data_url)
            source = "data.url"
            if not sessdata:
                sessdata = _extract_sessdata_from_cookie_header(
                    resp.header("Set-Cookie")
                )
                source = "Set-Cookie"

            # Diagnostic summary only — never print raw URLs or cookie
            # headers: they may carry the SESSDATA credential in plaintext
            # (see issue #7, P0).
            print(
                f"[debug] extract source={source} len={len(sessdata or '')}",
                file=sys.stderr,
            )

            if not sessdata or len(sessdata) < 20:
                # SESSDATA too short — likely extracted the wrong field.
                raise LoginExpired(
                    f"登录成功但未能提取有效的 SESSDATA "
                    f"(提取到 {len(sessdata or '')} 字符, source={source})"
                )

            save_session(sessdata)
            print("登录成功,凭证已保存。", file=sys.stderr)
            return sessdata

        if poll_code == 86038:
            # QR code expired — regenerate within the global budget
            # instead of failing outright (issue #7, P3).
            if refreshes < max_refreshes:
                refreshes += 1
                print(
                    "二维码已过期,已自动刷新,请重新扫码。",
                    file=sys.stderr,
                )
                qr_url, qrcode_key = _generate_qrcode(t)
                _show_qrcode(qr_url, on_qrcode)
                continue
            raise LoginExpired("二维码已失效,请重新运行 bili_sub2txt login")

        if poll_code == 86090:
            print("已扫码,请在手机上确认登录。", file=sys.stderr)

        # 86101 = waiting for scan — sleep and retry.
        _sleep(poll_interval)
        elapsed += poll_interval

    raise LoginExpired("登录超时,请重新运行 bili_sub2txt login")
