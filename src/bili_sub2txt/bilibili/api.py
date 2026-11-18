"""Bilibili API: video info, subtitle tracks, and subtitle download."""

import re
from dataclasses import dataclass
from typing import Any

from bili_sub2txt.bilibili.net import Transport, default_transport
from bili_sub2txt.bilibili.wbi import fetch_wbi_keys, sign
from bili_sub2txt.errors import BiliError, LoginExpired, NoSubtitle, VideoNotFound

BV_PATTERN = re.compile(r"BV[0-9A-Za-z]{10}")

VIEW_URL = "https://api.bilibili.com/x/web-interface/view"
PLAYER_URL = "https://api.bilibili.com/x/player/wbi/v2"
NAV_URL = "https://api.bilibili.com/x/web-interface/nav"


@dataclass
class VideoInfo:
    """Metadata for a Bilibili video."""

    title: str
    aid: int
    duration: int
    pages: list[dict[str, Any]]


@dataclass
class SubtitleTrack:
    """A single subtitle track from the player API."""

    lan: str
    lan_doc: str
    subtitle_url: str


@dataclass
class FetchedSubtitle:
    """A downloaded subtitle for one page of a video."""

    part_title: str
    json_text: str
    page_index: int


def parse_target(target: str) -> str:
    """Extract a BV number from *target* (bare BV, full URL, or b23.tv short link).

    Raises ``ValueError`` if no BV number can be found.
    """
    m = BV_PATTERN.search(target)
    if m:
        return m.group()
    raise ValueError(f"无法从输入中解析 BV 号: {target}")


def get_video_info(
    transport: Transport | None = None,
    sessdata: str | None = None,
    bvid: str = "",
) -> VideoInfo:
    """Fetch video metadata via the view API (works without login)."""
    t = transport or default_transport()
    cookies = {"SESSDATA": sessdata} if sessdata else None
    resp = t.request("GET", VIEW_URL, params={"bvid": bvid}, cookies=cookies)
    data = resp.json()
    code = data.get("code", -1)
    if code != 0:
        raise VideoNotFound(f"视频信息获取失败: code={code} {data.get('message', '')}")
    d = data["data"]
    return VideoInfo(
        title=d.get("title", ""),
        aid=d.get("aid", 0),
        duration=d.get("duration", 0),
        pages=d.get("pages", []),
    )


def list_subtitle_tracks(
    transport: Transport | None = None,
    sessdata: str | None = None,
    aid: int = 0,
    cid: int = 0,
) -> list[SubtitleTrack]:
    """Fetch subtitle tracks for one page via player/wbi/v2.

    Requires a valid ``SESSDATA``.  Raises ``LoginExpired`` if the session
    has expired (code -101) or ``NoSubtitle`` if the page has no subtitles.
    """
    t = transport or default_transport()
    cookies = {"SESSDATA": sessdata} if sessdata else None

    # WBI sign the request.  If key fetch fails, fall back to unsigned
    # (which may return wrong subtitles — the fetcher's duration cross-check
    # is the second line of defence).
    params: dict[str, Any] = {"aid": str(aid), "cid": str(cid)}
    try:
        img_key, sub_key = fetch_wbi_keys(t, cookies)
        if img_key and sub_key:
            params = sign(params, img_key, sub_key)
    except Exception:
        pass  # Unsigned fallback — the caller should be aware.

    resp = t.request(
        "GET",
        PLAYER_URL,
        params=params,
        cookies=cookies,
        headers={"Referer": "https://www.bilibili.com"},
    )
    data = resp.json()
    code = data.get("code", -1)
    if code == -101:
        raise LoginExpired("登录态失效,请运行 bili_sub2txt login 重新登录")
    if code != 0:
        raise BiliError(f"player 接口失败: code={code} {data.get('message', '')}")

    subtitles = ((data.get("data") or {}).get("subtitle") or {}).get("subtitles") or []
    if not subtitles:
        raise NoSubtitle("该分 P 没有可用字幕")

    return [
        SubtitleTrack(
            lan=s.get("lan", ""),
            lan_doc=s.get("lan_doc", ""),
            subtitle_url=s.get("subtitle_url", ""),
        )
        for s in subtitles
    ]


def select_track(
    tracks: list[SubtitleTrack],
    *,
    lang: str | None = None,
) -> SubtitleTrack:
    """Choose one subtitle track.

    With *lang*: exact / prefix / ``lan_doc`` substring match.
    Without *lang*: prefer human Chinese > AI Chinese > human English >
    AI English > other.
    """
    if not tracks:
        raise NoSubtitle("无可用字幕轨道")

    if lang:
        # Exact match.
        for t in tracks:
            if t.lan == lang:
                return t
        # Prefix match (bidirectional).
        for t in tracks:
            if t.lan.startswith(lang) or lang.startswith(t.lan):
                return t
        # Match after stripping AI prefix (e.g. "ja" → "ai-ja").
        for t in tracks:
            base = t.lan.replace("ai-", "", 1) if t.lan.startswith("ai-") else t.lan
            if base == lang or base.startswith(lang) or lang.startswith(base):
                return t
        # lan_doc substring.
        for t in tracks:
            if lang in t.lan_doc:
                return t
        available = [(t.lan, t.lan_doc) for t in tracks]
        raise NoSubtitle(f"未找到语言 '{lang}',可用轨道: {available}")

    def score(t: SubtitleTrack) -> int:
        lan = t.lan.lower()
        is_ai = lan.startswith("ai-")
        base = lan.replace("ai-", "", 1) if is_ai else lan
        if base.startswith("zh"):
            return 0 if not is_ai else 1
        if base.startswith("en"):
            return 2 if not is_ai else 3
        return 4

    return min(tracks, key=score)


def download_subtitle(
    transport: Transport | None = None,
    track: SubtitleTrack | None = None,
) -> str:
    """Download the subtitle JSON text for *track*."""
    if track is None:
        raise ValueError("track is required")
    t = transport or default_transport()
    url = track.subtitle_url
    # Bilibili returns protocol-relative URLs (//aisubtitle.hdslb.com/...).
    if url.startswith("//"):
        url = "https:" + url
    resp = t.request(
        "GET",
        url,
        headers={"Referer": "https://www.bilibili.com"},
    )
    return resp.text


def fetch_subtitle_json(
    transport: Transport | None = None,
    sessdata: str | None = None,
    bvid: str = "",
    *,
    lang: str | None = None,
) -> tuple[VideoInfo, list[FetchedSubtitle]]:
    """High-level: fetch video info + all pages' subtitle JSON.

    Returns ``(VideoInfo, [FetchedSubtitle, ...])``.  Pages without
    subtitles are silently skipped.  If no page yields subtitles,
    ``NoSubtitle`` is raised.
    """
    info = get_video_info(transport, sessdata, bvid)

    results: list[FetchedSubtitle] = []
    for page in info.pages:
        cid = page.get("cid", 0)
        part = page.get("part", "")
        page_index = page.get("page", 1)
        try:
            tracks = list_subtitle_tracks(transport, sessdata, info.aid, cid)
            track = select_track(tracks, lang=lang)
            json_text = download_subtitle(transport, track)
            results.append(
                FetchedSubtitle(
                    part_title=part,
                    json_text=json_text,
                    page_index=page_index,
                )
            )
        except NoSubtitle:
            # When a specific language is requested, surface the error
            # immediately so the user sees the available tracks.
            if lang is not None:
                raise
            continue

    if not results:
        raise NoSubtitle("全部分 P 均无可用字幕")

    return info, results
