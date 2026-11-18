"""Tests for the QR-code login flow."""

import pytest

from bili_sub2txt.bilibili.auth import (
    _extract_sessdata_from_cookie_header,
    _extract_sessdata_from_url,
    login,
    render_qrcode,
)
from bili_sub2txt.errors import LoginExpired
from tests.conftest import FakeTransport

GENERATE_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
POLL_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"


class TestExtractSessdata:
    def test_from_url(self):
        url = "https://api.bilibili.com/x/passport-login/web/crossDomain?SESSDATA=abc123&DedeUserID=1"
        assert _extract_sessdata_from_url(url) == "abc123"

    def test_from_url_missing(self):
        assert _extract_sessdata_from_url("https://example.com/no-sessdata") is None

    def test_from_cookie_header(self):
        assert _extract_sessdata_from_cookie_header("SESSDATA=xyz; Path=/; HttpOnly") == "xyz"

    def test_from_cookie_header_missing(self):
        assert _extract_sessdata_from_cookie_header("other=val") is None

    def test_from_cookie_header_none(self):
        assert _extract_sessdata_from_cookie_header(None) is None


class TestRenderQrcode:
    def test_returns_string(self):
        result = render_qrcode("https://example.com")
        assert isinstance(result, str)
        assert len(result) > 0


class TestLogin:
    def test_success_from_url(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BILI_SUB2TXT_SESSION_DIR", str(tmp_path))
        t = FakeTransport()
        t.route(GENERATE_URL, body={
            "code": 0,
            "data": {"url": "https://q.example.com", "qrcode_key": "key123"},
        })
        t.route_sequence(POLL_URL, [
            {"body": {"code": 0, "data": {"code": 86101}}},
            {"body": {"code": 0, "data": {
                "code": 0,
                "url": "https://api.bilibili.com/x/passport-login/web/crossDomain?SESSDATA=this_is_a_long_enough_sessdata_value",
            }}},
        ])

        no_sleep = lambda _: None
        sessdata = login(t, poll_interval=0.01, max_wait=5, _sleep=no_sleep)
        assert sessdata == "this_is_a_long_enough_sessdata_value"

    def test_qr_expired(self, monkeypatch):
        t = FakeTransport()
        t.route(GENERATE_URL, body={
            "code": 0,
            "data": {"url": "https://q.example.com", "qrcode_key": "key123"},
        })
        t.route(POLL_URL, params={"qrcode_key": "key123"}, body={
            "code": 0, "data": {"code": 86038},
        })

        with pytest.raises(LoginExpired, match="二维码已失效"):
            login(t, poll_interval=0.01, max_wait=5, _sleep=lambda _: None)

    def test_generate_failure(self):
        t = FakeTransport()
        t.route(GENERATE_URL, body={"code": -509, "message": "too frequent"})
        with pytest.raises(LoginExpired, match="二维码生成失败"):
            login(t, poll_interval=0.01, max_wait=5, _sleep=lambda _: None)

    def test_success_from_set_cookie(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BILI_SUB2TXT_SESSION_DIR", str(tmp_path))
        t = FakeTransport()
        t.route(GENERATE_URL, body={
            "code": 0,
            "data": {"url": "https://q.example.com", "qrcode_key": "key123"},
        })
        t.route_sequence(POLL_URL, [
            {"body": {"code": 0, "data": {"code": 0, "url": ""}}},
        ])
        # Override the first (and only) sequence response with Set-Cookie.
        t._sequences[POLL_URL][0]._headers["set-cookie"] = "SESSDATA=this_is_a_long_cookie_sessdata; Path=/"

        sessdata = login(t, poll_interval=0.01, max_wait=5, _sleep=lambda _: None)
        assert sessdata == "this_is_a_long_cookie_sessdata"

    @pytest.mark.parametrize("source_url,cookie_header", [
        # Credential comes from data.url query string.
        ("https://api.bilibili.com/crossDomain?SESSDATA=secret_from_url_0123456789", None),
        # Credential comes from the Set-Cookie header.
        ("", "SESSDATA=secret_from_cookie_0123456789; Path=/; HttpOnly"),
    ])
    def test_success_output_does_not_leak_sessdata(
        self, tmp_path, monkeypatch, capsys, source_url, cookie_header
    ):
        """Regression for issue #7 (P0): login output must never contain
        the plaintext SESSDATA, regardless of the extraction source."""
        monkeypatch.setenv("BILI_SUB2TXT_SESSION_DIR", str(tmp_path))
        t = FakeTransport()
        t.route(GENERATE_URL, body={
            "code": 0,
            "data": {"url": "https://q.example.com", "qrcode_key": "key123"},
        })
        t.route_sequence(POLL_URL, [
            {"body": {"code": 0, "data": {"code": 0, "url": source_url}}},
        ])
        if cookie_header:
            t._sequences[POLL_URL][0]._headers["set-cookie"] = cookie_header

        login(t, poll_interval=0.01, max_wait=5, _sleep=lambda _: None)

        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "secret_from_url_0123456789" not in combined
        assert "secret_from_cookie_0123456789" not in combined
        # Diagnostic summary is still present (source and length only).
        assert "[debug] extract source=" in combined

    def test_on_status_callback(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BILI_SUB2TXT_SESSION_DIR", str(tmp_path))
        statuses = []
        t = FakeTransport()
        t.route(GENERATE_URL, body={
            "code": 0,
            "data": {"url": "https://q.example.com", "qrcode_key": "key123"},
        })
        t.route_sequence(POLL_URL, [
            {"body": {"code": 0, "data": {"code": 86101}}},
            {"body": {"code": 0, "data": {
                "code": 0,
                "url": "https://api.bilibili.com/?SESSDATA=this_is_a_long_ok_sessdata",
            }}},
        ])

        login(t, on_status=lambda code, data: statuses.append(code),
              poll_interval=0.01, max_wait=5, _sleep=lambda _: None)
        assert 86101 in statuses
        assert 0 in statuses
