"""Tests for the HTTP transport layer and FakeTransport."""

import pytest

from vtt2txt.bilibili.net import HttpResponse, default_transport, set_default_transport
from tests.conftest import FakeTransport


class TestHttpResponse:
    def test_json(self):
        r = HttpResponse(200, b'{"code": 0}', {"Content-Type": "application/json"})
        assert r.json() == {"code": 0}

    def test_text(self):
        r = HttpResponse(200, "hello".encode("utf-8"))
        assert r.text == "hello"

    def test_header_case_insensitive(self):
        r = HttpResponse(200, b"", {"Set-Cookie": "SESSDATA=abc"})
        assert r.header("set-cookie") == "SESSDATA=abc"
        assert r.header("SET-COOKIE") == "SESSDATA=abc"
        assert r.header("missing") is None


class TestFakeTransport:
    def test_route_match_no_params(self):
        t = FakeTransport()
        t.route("https://api.example.com/data", body={"code": 0})
        resp = t.request("GET", "https://api.example.com/data")
        assert resp.json() == {"code": 0}

    def test_route_params_subset_match(self):
        t = FakeTransport()
        t.route("https://api.example.com/data", params={"aid": 123}, body={"code": 0})
        # Extra params (wts, w_rid) are ignored — only preset keys are checked.
        resp = t.request(
            "GET",
            "https://api.example.com/data",
            params={"aid": 123, "wts": 999, "w_rid": "abc"},
        )
        assert resp.status == 200

    def test_no_match_raises(self):
        t = FakeTransport()
        with pytest.raises(AssertionError, match="unexpected request"):
            t.request("GET", "https://api.example.com/nope")

    def test_route_sequence(self):
        t = FakeTransport()
        t.route_sequence(
            "https://api.example.com/poll",
            [
                {"body": {"code": 86101}},
                {"body": {"code": 0, "data": {"url": "https://b23.tv/abc"}}},
            ],
        )
        r1 = t.request("GET", "https://api.example.com/poll")
        r2 = t.request("GET", "https://api.example.com/poll")
        assert r1.json()["code"] == 86101
        assert r2.json()["code"] == 0

    def test_calls_recorded(self):
        t = FakeTransport()
        t.route("https://api.example.com/data", body={})
        t.request("GET", "https://api.example.com/data",
                  params={"aid": 1}, cookies={"SESSDATA": "secret"})
        assert len(t.calls) == 1
        assert t.calls[0].cookies == {"SESSDATA": "secret"}
