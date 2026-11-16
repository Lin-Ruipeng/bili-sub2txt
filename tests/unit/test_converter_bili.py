"""Tests for convert_bili_json — Bilibili JSON subtitle conversion."""

import json

import pytest

from vtt2txt.converter import convert_bili_json
from vtt2txt.errors import BiliError


def _json(body):
    """Helper: wrap a body list into the expected JSON string."""
    return json.dumps({"body": body}, ensure_ascii=False)


class TestConvertBiliJson:
    def test_normal_body(self):
        content = _json([
            {"from": 0.0, "to": 1.14, "content": "你好"},
            {"from": 1.14, "to": 2.5, "content": "世界"},
        ])
        assert convert_bili_json(content) == "你好\n世界"

    def test_body_missing_returns_empty(self):
        assert convert_bili_json(json.dumps({})) == ""

    def test_body_not_list_returns_empty(self):
        assert convert_bili_json(json.dumps({"body": "not-a-list"})) == ""

    def test_empty_body_returns_empty(self):
        assert convert_bili_json(json.dumps({"body": []})) == ""

    def test_item_missing_content_skipped(self):
        content = _json([
            {"from": 0, "to": 1},
            {"from": 1, "to": 2, "content": "有内容"},
        ])
        assert convert_bili_json(content) == "有内容"

    def test_empty_content_skipped(self):
        content = _json([
            {"content": ""},
            {"content": "  "},
            {"content": "有效"},
        ])
        assert convert_bili_json(content) == "有效"

    def test_html_entities_and_tags_cleaned(self):
        content = _json([
            {"content": "<v Speaker>你好 &amp; <i>再见</i> &nbsp;"},
        ])
        assert convert_bili_json(content) == "你好 & 再见"

    def test_text_key_fallback(self):
        content = json.dumps({"body": [{"text": "用text键"}]}, ensure_ascii=False)
        assert convert_bili_json(content) == "用text键"

    def test_json_parse_error_raises(self):
        with pytest.raises(BiliError, match="JSON 解析失败"):
            convert_bili_json("not valid json")

    def test_all_missing_content_raises(self):
        """Field-drift protection: body non-empty but no recognised text key."""
        content = _json([
            {"from": 0, "to": 1},
            {"from": 1, "to": 2},
        ])
        with pytest.raises(BiliError, match="无法识别"):
            convert_bili_json(content)

    def test_no_trailing_newline(self):
        content = _json([{"content": "一行"}])
        result = convert_bili_json(content)
        assert not result.endswith("\n")

    def test_multiline_content_preserved(self):
        content = _json([{"content": "第一行\n第二行"}])
        assert convert_bili_json(content) == "第一行\n第二行"
