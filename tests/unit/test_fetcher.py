"""Tests for the fetch orchestrator."""

import json
from pathlib import Path

import pytest

from bili_sub2txt.bilibili.fetcher import _cross_check_duration, fetch
from bili_sub2txt.errors import EXIT_GENERIC, EXIT_LOGIN, EXIT_OK
from tests.conftest import FakeTransport

VIEW_URL = "https://api.bilibili.com/x/web-interface/view"
PLAYER_URL = "https://api.bilibili.com/x/player/wbi/v2"
NAV_URL = "https://api.bilibili.com/x/web-interface/nav"
TEST_BV = "BV1jJ4m1J7ba"


def _setup_video(t, *, pages=None, subtitles_per_page=None, subtitle_body=None):
    """Wire up a FakeTransport with a full view→nav→player→subtitle chain."""
    pages = pages or [{"cid": 100, "page": 1, "part": "第一集"}]
    subtitles_per_page = subtitles_per_page or {100: ["zh-Hans"]}
    subtitle_body = subtitle_body or {"body": [{"from": 0, "to": 5, "content": "测试字幕"}]}

    t.route(VIEW_URL, params={"bvid": TEST_BV}, body={
        "code": 0, "data": {
            "title": "测试视频", "aid": 1, "duration": 60, "pages": pages,
        }
    })
    t.route(NAV_URL, body={
        "code": 0, "data": {"wbi_img": {
            "img_url": "https://x.com/" + "a" * 32 + ".png",
            "sub_url": "https://x.com/" + "b" * 32 + ".png",
        }}
    })
    for page in pages:
        cid = page["cid"]
        subs = subtitles_per_page.get(cid, [])
        if subs:
            sub_list = []
            for lan in subs:
                url = f"https://sub.example.com/{cid}_{lan}.json"
                sub_list.append({"lan": lan, "lan_doc": lan, "subtitle_url": url})
                t.route(url, body=subtitle_body)
            t.route(PLAYER_URL, params={"aid": "1", "cid": str(cid)}, body={
                "code": 0, "data": {"subtitle": {"subtitles": sub_list}},
            })
        else:
            t.route(PLAYER_URL, params={"aid": "1", "cid": str(cid)}, body={
                "code": 0, "data": {"subtitle": {"subtitles": []}},
            })


class TestCrossCheckDuration:
    def test_within_range(self):
        json_text = json.dumps({"body": [{"to": 55}]})
        assert _cross_check_duration(json_text, 60) is True

    def test_too_short(self):
        json_text = json.dumps({"body": [{"to": 10}]})
        assert _cross_check_duration(json_text, 60) is False

    def test_too_long(self):
        json_text = json.dumps({"body": [{"to": 100}]})
        assert _cross_check_duration(json_text, 60) is False

    def test_no_expected_duration(self):
        assert _cross_check_duration("{}", 0) is True

    def test_unparseable(self):
        assert _cross_check_duration("not json", 60) is True


class TestFetch:
    def test_single_page_success(self, tmp_path, capsys):
        t = FakeTransport()
        _setup_video(t)
        code = fetch(TEST_BV, output_dir=tmp_path, transport=t, sessdata="sess")
        assert code == EXIT_OK
        out_file = tmp_path / TEST_BV / "第一集.txt"
        assert out_file.exists()
        assert "测试字幕" in out_file.read_text(encoding="utf-8")

    def test_multi_page_success(self, tmp_path):
        t = FakeTransport()
        _setup_video(t, pages=[
            {"cid": 100, "page": 1, "part": "第一集"},
            {"cid": 200, "page": 2, "part": "第二集"},
        ], subtitles_per_page={
            100: ["zh-Hans"],
            200: ["zh-Hans"],
        })
        code = fetch(TEST_BV, output_dir=tmp_path, transport=t, sessdata="sess")
        assert code == EXIT_OK
        assert (tmp_path / TEST_BV / "01_第一集.txt").exists()
        assert (tmp_path / TEST_BV / "02_第二集.txt").exists()

    def test_duration_warning_does_not_block(self, tmp_path, capsys):
        t = FakeTransport()
        _setup_video(t, subtitle_body={"body": [{"to": 5, "content": "短字幕"}]})
        code = fetch(TEST_BV, output_dir=tmp_path, transport=t, sessdata="sess")
        # Duration 5 vs expected 60 → ratio 0.083 < 0.5 → warning
        captured = capsys.readouterr()
        assert "时长差异" in captured.err
        assert code == EXIT_OK  # still succeeds
        assert (tmp_path / TEST_BV / "第一集.txt").exists()

    def test_no_subtitle_without_sessdata_returns_login(self, tmp_path, capsys):
        t = FakeTransport()
        _setup_video(t, subtitles_per_page={100: []})
        code = fetch(TEST_BV, output_dir=tmp_path, transport=t, sessdata=None)
        assert code == EXIT_LOGIN
        assert "需要登录" in capsys.readouterr().err

    def test_no_subtitle_with_sessdata_returns_generic(self, tmp_path, capsys):
        t = FakeTransport()
        _setup_video(t, subtitles_per_page={100: []})
        code = fetch(TEST_BV, output_dir=tmp_path, transport=t, sessdata="sess")
        assert code == EXIT_GENERIC
        assert "下载失败" in capsys.readouterr().err

    def test_output_dir_auto_created(self, tmp_path):
        t = FakeTransport()
        _setup_video(t)
        out = tmp_path / "deep" / "nested"
        code = fetch(TEST_BV, output_dir=out, transport=t, sessdata="sess")
        assert code == EXIT_OK
        assert (out / TEST_BV / "第一集.txt").exists()
