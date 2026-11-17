"""QR-code login via Bilibili's Web passport API.

Flow:
  1. ``/qrcode/generate`` → ``{url, qrcode_key}``
  2. Render QR code (``qrcode`` package if installed, else print URL)
  3. Poll ``/qrcode/poll`` every *poll_interval* seconds:
     - 86101 = waiting for scan
     - 86090 = scanned, awaiting confirmation
     - 86038 = QR code expired → ``LoginExpired``
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
    """Render *url* as a terminal QR code, or fall back to printing the URL."""
    try:
        import qrcode

        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        matrix = qr.get_matrix()
        lines = [
            "".join("  " if cell else "\u2588\u2588" for cell in row)
            for row in matrix
        ]
        return "\n".join(lines)
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


def login(
    transport: Transport | None = None,
    *,
    on_status=None,
    poll_interval: float = 2.0,
    max_wait: float = 180.0,
    _sleep=time.sleep,
) -> str:
    """Perform QR-code login and persist the session.

    Returns the ``SESSDATA`` string on success.  Raises ``LoginExpired``
    on timeout or QR-code expiry.
    """
    t = transport or default_transport()

    # Step 1: generate QR code.
    resp = t.request("GET", GENERATE_URL)
    data = resp.json()
    if data.get("code") != 0:
        raise LoginExpired(
            f"二维码生成失败: {data.get('message', '')}"
        )

    qr_url = data["data"]["url"]
    qrcode_key = data["data"]["qrcode_key"]

    print(render_qrcode(qr_url))
    print("\n请使用 B 站手机客户端扫描上方二维码登录。", file=sys.stderr)

    # Step 2: poll until success, expiry, or timeout.
    elapsed = 0.0
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

            # Diagnostic output (always print on success for debugging).
            print(
                f"[debug] extract source={source} len={len(sessdata or '')} "
                f"url={data_url[:200]}",
                file=sys.stderr,
            )
            set_cookie_raw = resp.header("Set-Cookie") or ""
            print(
                f"[debug] Set-Cookie={set_cookie_raw[:300]}",
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
            raise LoginExpired("二维码已失效,请重新运行 bili_sub2txt login")

        if poll_code == 86090:
            print("已扫码,请在手机上确认登录。", file=sys.stderr)

        # 86101 = waiting for scan — sleep and retry.
        _sleep(poll_interval)
        elapsed += poll_interval

    raise LoginExpired("登录超时,请重新运行 bili_sub2txt login")
