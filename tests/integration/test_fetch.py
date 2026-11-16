"""End-to-end integration tests for the fetch command via CLI main()."""

import json
from pathlib import Path

import pytest

from vtt2txt.cli import main
from tests.conftest import FakeTransport

VIEW_URL = "https://api.bilibili.com/x/web-interface/view"
PLAYER_URL = "https://api.bilibili.com/x/player/wbi/v2"
NAV_URL = "https://api.bilibili.com/x/web-interface/nav"
TEST_BV = "BV1jJ4m1J7ba"


def _wire_transport(t, *, pages=None, subtitle_body=None):
    pages = pages or [{"cid": 100, "page": 1, "part": "第一集"}]
    subtitle_body = subtitle_body or {
        "body": [{"from": 0, "to": 5, "content": "集成测试字幕"}]
    }

    t.route(VIEW_URL, params={"bvid": TEST_BV}, body={
        "code": 0, "data": {
            "title": "集成测试视频", "aid": 1, "duration": 60, "pages": pages,
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
        url = f"https://sub.example.com/{cid}.json"
        t.route(PLAYER_URL, params={"aid": "1", "cid": str(cid)}, body={
            "code": 0,
            "data": {"subtitle": {"subtitles": [
                {"lan": "zh-Hans", "lan_doc": "中文", "subtitle_url": url},
            ]}},
        })
        t.route(url, body=subtitle_body)


class TestFetchIntegration:
    def test_single_page_e2e(self, tmp_path, monkeypatch):
        t = FakeTransport()
        _wire_transport(t)
        monkeypatch.setattr("vtt2txt.bilibili.net._default", t)
        monkeypatch.setattr("vtt2txt.cli.get_sessdata", lambda: "fake_sess")

        code = main(["fetch", TEST_BV, "--output", str(tmp_path)])
        assert code == 0
        out = tmp_path / TEST_BV / "第一集.txt"
        assert out.exists()
        assert "集成测试字幕" in out.read_text(encoding="utf-8")

    def test_multi_page_e2e(self, tmp_path, monkeypatch):
        t = FakeTransport()
        _wire_transport(t, pages=[
            {"cid": 100, "page": 1, "part": "上集"},
            {"cid": 200, "page": 2, "part": "下集"},
        ])
        monkeypatch.setattr("vtt2txt.bilibili.net._default", t)
        monkeypatch.setattr("vtt2txt.cli.get_sessdata", lambda: "fake_sess")

        code = main(["fetch", TEST_BV, "--output", str(tmp_path)])
        assert code == 0
        assert (tmp_path / TEST_BV / "01_上集.txt").exists()
        assert (tmp_path / TEST_BV / "02_下集.txt").exists()

    def test_duration_warning_does_not_block(self, tmp_path, monkeypatch, capsys):
        t = FakeTransport()
        _wire_transport(t, subtitle_body={
            "body": [{"from": 0, "to": 3, "content": "很短"}]
        })
        monkeypatch.setattr("vtt2txt.bilibili.net._default", t)
        monkeypatch.setattr("vtt2txt.cli.get_sessdata", lambda: "fake_sess")

        code = main(["fetch", TEST_BV, "--output", str(tmp_path)])
        assert code == 0
        captured = capsys.readouterr()
        assert "时长差异" in captured.err
        assert (tmp_path / TEST_BV / "第一集.txt").exists()
