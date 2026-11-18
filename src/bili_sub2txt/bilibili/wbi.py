"""WBI signature for Bilibili API authentication.

The WBI signature scheme combines an *img_key* and *sub_key* (fetched from
``/x/web-interface/nav``) into a *mixin_key* via a fixed 64-entry permutation
table, then signs request parameters with MD5.

The permutation table is hardcoded and may change when Bilibili updates it.
If signatures stop working, verify the table against the current value.
"""

import hashlib
import time
from typing import Any

# 64-entry permutation table (public, community-maintained).
MIXIN_KEY_ENC_TAB: tuple[int, ...] = (
    46,
    47,
    18,
    2,
    53,
    8,
    23,
    32,
    15,
    50,
    10,
    31,
    58,
    3,
    45,
    35,
    27,
    43,
    5,
    49,
    33,
    9,
    42,
    19,
    29,
    28,
    14,
    39,
    12,
    38,
    41,
    13,
    37,
    48,
    7,
    16,
    24,
    55,
    40,
    61,
    26,
    17,
    0,
    1,
    60,
    51,
    30,
    4,
    22,
    25,
    54,
    21,
    56,
    59,
    6,
    63,
    57,
    62,
    11,
    36,
    20,
    34,
    44,
    52,
)

# Characters stripped from parameter values before signing.
_FILTER_CHARS = set("!'()*")


def get_mixin_key(img_key: str, sub_key: str) -> str:
    """Derive the 32-character *mixin_key* from *img_key* + *sub_key*."""
    raw = img_key + sub_key
    return "".join(raw[i] for i in MIXIN_KEY_ENC_TAB)[:32]


def sign(
    params: dict[str, Any],
    img_key: str,
    sub_key: str,
    wts: int | None = None,
) -> dict[str, Any]:
    """Sign *params* with WBI, returning a new dict including ``wts`` and ``w_rid``."""
    mixin_key = get_mixin_key(img_key, sub_key)
    if wts is None:
        wts = int(time.time())

    signed: dict[str, str] = {}
    for k, v in params.items():
        signed[k] = "".join(ch for ch in str(v) if ch not in _FILTER_CHARS)
    signed["wts"] = str(wts)

    # Sort by key, build query string, append mixin_key, MD5.
    query = "&".join(f"{k}={signed[k]}" for k in sorted(signed))
    w_rid = hashlib.md5((query + mixin_key).encode()).hexdigest()
    signed["w_rid"] = w_rid
    return signed


def fetch_wbi_keys(transport, cookies: dict[str, str] | None = None) -> tuple[str, str]:
    """Fetch *img_key* and *sub_key* from ``/x/web-interface/nav``."""
    resp = transport.request(
        "GET",
        "https://api.bilibili.com/x/web-interface/nav",
        cookies=cookies,
    )
    data = resp.json()
    wbi_img = (data.get("data") or {}).get("wbi_img") or {}
    img_url = wbi_img.get("img_url", "")
    sub_url = wbi_img.get("sub_url", "")
    img_key = img_url.rsplit("/", 1)[-1].split(".")[0] if img_url else ""
    sub_key = sub_url.rsplit("/", 1)[-1].split(".")[0] if sub_url else ""
    return img_key, sub_key
