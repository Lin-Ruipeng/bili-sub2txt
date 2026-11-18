"""Tests for the Bilibili API layer."""

from typing import ClassVar

import pytest

from bili_sub2txt.bilibili.api import (
    SubtitleTrack,
    download_subtitle,
    fetch_subtitle_json,
    get_video_info,
    list_subtitle_tracks,
    parse_target,
    select_track,
)
from bili_sub2txt.errors import LoginExpired, NoSubtitle, VideoNotFound
from tests.conftest import FakeTransport

VIEW_URL = "https://api.bilibili.com/x/web-interface/view"
PLAYER_URL = "https://api.bilibili.com/x/player/wbi/v2"
NAV_URL = "https://api.bilibili.com/x/web-interface/nav"


class TestParseTarget:
    def test_bare_bv(self):
        assert parse_target("BV1jJ4m1J7ba") == "BV1jJ4m1J7ba"

    def test_full_url(self):
        assert parse_target("https://www.bilibili.com/video/BV1jJ4m1J7ba/") == "BV1jJ4m1J7ba"

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="无法从输入中解析 BV 号"):
            parse_target("not-a-bv")

    def test_bv_embedded_in_text(self):
        assert parse_target("看这个 https://b23.tv/BV1jJ4m1J7ba 好看") == "BV1jJ4m1J7ba"


class TestGetVideoInfo:
    def test_success(self):
        t = FakeTransport()
        t.route(
            VIEW_URL,
            params={"bvid": "BV1xx"},
            body={
                "code": 0,
                "data": {
                    "title": "测试视频",
                    "aid": 123,
                    "duration": 60,
                    "pages": [{"cid": 456, "page": 1, "part": "第一集"}],
                },
            },
        )
        info = get_video_info(t, None, "BV1xx")
        assert info.title == "测试视频"
        assert info.aid == 123
        assert info.duration == 60
        assert len(info.pages) == 1

    def test_not_found(self):
        t = FakeTransport()
        t.route(VIEW_URL, params={"bvid": "BV1xx"}, body={"code": -404, "message": "不存在"})
        with pytest.raises(VideoNotFound, match="不存在"):
            get_video_info(t, None, "BV1xx")


class TestListSubtitleTracks:
    def _setup_nav(self, t):
        t.route(
            NAV_URL,
            body={
                "code": 0,
                "data": {
                    "wbi_img": {
                        "img_url": "https://x.com/a" + "b" * 32 + ".png",
                        "sub_url": "https://x.com/c" + "d" * 32 + ".png",
                    }
                },
            },
        )

    def test_success(self):
        t = FakeTransport()
        self._setup_nav(t)
        t.route(
            PLAYER_URL,
            params={"aid": "123", "cid": "456"},
            body={
                "code": 0,
                "data": {
                    "subtitle": {
                        "subtitles": [
                            {
                                "lan": "zh-Hans",
                                "lan_doc": "中文（简体）",
                                "subtitle_url": "https://sub.example.com/1.json",
                            },
                            {
                                "lan": "ai-zh",
                                "lan_doc": "AI识别字幕",
                                "subtitle_url": "https://sub.example.com/2.json",
                            },
                        ]
                    }
                },
            },
        )
        tracks = list_subtitle_tracks(t, "sess", 123, 456)
        assert len(tracks) == 2
        assert tracks[0].lan == "zh-Hans"

    def test_empty_raises_no_subtitle(self):
        t = FakeTransport()
        self._setup_nav(t)
        t.route(
            PLAYER_URL,
            params={"aid": "123", "cid": "456"},
            body={
                "code": 0,
                "data": {"subtitle": {"subtitles": []}},
            },
        )
        with pytest.raises(NoSubtitle):
            list_subtitle_tracks(t, "sess", 123, 456)

    def test_login_expired(self):
        t = FakeTransport()
        self._setup_nav(t)
        t.route(
            PLAYER_URL,
            params={"aid": "123", "cid": "456"},
            body={
                "code": -101,
                "message": "账号未登录",
            },
        )
        with pytest.raises(LoginExpired):
            list_subtitle_tracks(t, "sess", 123, 456)


class TestSelectTrack:
    tracks: ClassVar[list[SubtitleTrack]] = [
        SubtitleTrack("zh-Hans", "中文简体", "url1"),
        SubtitleTrack("ai-zh", "AI字幕", "url2"),
        SubtitleTrack("en", "英文", "url3"),
    ]

    def test_prefers_human_chinese(self):
        assert select_track(self.tracks).lan == "zh-Hans"

    def test_lang_exact(self):
        assert select_track(self.tracks, lang="en").lan == "en"

    def test_lang_prefix(self):
        assert select_track(self.tracks, lang="zh").lan == "zh-Hans"

    def test_lang_not_found(self):
        with pytest.raises(NoSubtitle, match="未找到语言"):
            select_track(self.tracks, lang="ja")

    def test_empty_raises(self):
        with pytest.raises(NoSubtitle):
            select_track([])


class TestDownloadSubtitle:
    def test_returns_text(self):
        t = FakeTransport()
        t.route(
            "https://sub.example.com/1.json", body={"body": [{"from": 0, "to": 1, "content": "hi"}]}
        )
        track = SubtitleTrack("zh", "中文", "https://sub.example.com/1.json")
        text = download_subtitle(t, track)
        assert "body" in text
        # Verify Referer was sent.
        assert t.calls[0].headers is not None
        assert t.calls[0].headers.get("Referer") == "https://www.bilibili.com"


class TestFetchSubtitleJson:
    def test_multi_page(self):
        t = FakeTransport()
        t.route(
            VIEW_URL,
            params={"bvid": "BV1xx"},
            body={
                "code": 0,
                "data": {
                    "title": "多P视频",
                    "aid": 1,
                    "duration": 120,
                    "pages": [
                        {"cid": 10, "page": 1, "part": "第一集"},
                        {"cid": 20, "page": 2, "part": "第二集"},
                    ],
                },
            },
        )
        t.route(
            NAV_URL,
            body={
                "code": 0,
                "data": {
                    "wbi_img": {
                        "img_url": "https://x.com/" + "a" * 32 + ".png",
                        "sub_url": "https://x.com/" + "b" * 32 + ".png",
                    }
                },
            },
        )
        t.route(
            PLAYER_URL,
            params={"aid": "1", "cid": "10"},
            body={
                "code": 0,
                "data": {
                    "subtitle": {
                        "subtitles": [
                            {
                                "lan": "zh-Hans",
                                "lan_doc": "中文",
                                "subtitle_url": "https://sub/1.json",
                            },
                        ]
                    }
                },
            },
        )
        t.route(
            PLAYER_URL,
            params={"aid": "1", "cid": "20"},
            body={
                "code": 0,
                "data": {"subtitle": {"subtitles": []}},
            },
        )
        t.route("https://sub/1.json", body={"body": [{"content": "hello"}]})

        info, results = fetch_subtitle_json(t, "sess", "BV1xx")
        assert info.title == "多P视频"
        assert len(results) == 1
        assert results[0].part_title == "第一集"
        assert "hello" in results[0].json_text
