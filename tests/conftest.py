"""Shared test fixtures — FakeTransport for offline HTTP mocking."""

import json
from dataclasses import dataclass
from typing import Any

from bili_sub2txt.bilibili.net import HttpResponse


@dataclass
class CallRecord:
    """A recorded HTTP call for assertion in tests."""

    method: str
    url: str
    params: dict[str, Any] | None
    cookies: dict[str, str] | None
    headers: dict[str, str] | None


def _encode_body(body: Any) -> bytes:
    if isinstance(body, (dict, list)):
        return json.dumps(body).encode("utf-8")
    if isinstance(body, str):
        return body.encode("utf-8")
    if isinstance(body, bytes):
        return body
    return b""


class FakeTransport:
    """A test transport that returns preset responses.

    Usage::

        t = FakeTransport()
        t.route("https://api.example.com/data",
                params={"aid": 123},
                body={"code": 0, "data": {...}})
        resp = t.request("GET", "https://api.example.com/data",
                         params={"aid": 123, "wts": 999})
        assert resp.json()["code"] == 0

    Parameter matching is *subset*: only keys present in the route's
    ``params`` are checked, so dynamic values (``wts``, ``w_rid``) are
    ignored.
    """

    def __init__(self):
        self._routes: list[tuple[str, dict | None, HttpResponse]] = []
        self._sequences: dict[str, list[HttpResponse]] = {}
        self.calls: list[CallRecord] = []

    def route(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        status: int = 200,
        body: Any = None,
        headers: dict[str, str] | None = None,
    ) -> "FakeTransport":
        """Register a response for *url*, optionally matching *params* subset."""
        resp_headers = dict(headers or {})
        if isinstance(body, (dict, list)):
            resp_headers.setdefault("Content-Type", "application/json")
        resp = HttpResponse(status, _encode_body(body), resp_headers)
        self._routes.append((url, params, resp))
        return self

    def route_sequence(self, url: str, responses: list[dict]) -> "FakeTransport":
        """Register a sequence of responses for repeated calls to *url*."""
        seq = []
        for r in responses:
            seq.append(
                HttpResponse(
                    r.get("status", 200),
                    _encode_body(r.get("body")),
                    r.get("headers", {}),
                )
            )
        self._sequences[url] = seq
        return self

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        cookies: dict[str, str] | None = None,
        timeout: float = 10.0,
    ) -> HttpResponse:
        self.calls.append(CallRecord(method, url, params, cookies, headers))

        # Check sequences first (for poll-style tests).
        if url in self._sequences:
            seq = self._sequences[url]
            if seq:
                return seq.pop(0)
            raise AssertionError(f"sequence exhausted for {url}")

        # Match routes by URL + params subset.
        for route_url, route_params, resp in self._routes:
            if url != route_url:
                continue
            if route_params is None:
                return resp
            if params is None:
                params = {}
            if all(params.get(k) == v for k, v in route_params.items()):
                return resp

        raise AssertionError(
            f"unexpected request: {method} {url} params={params}"
        )
