"""Tests for exceptions, exit codes, and redaction."""

import pytest

from bili_sub2txt.errors import (
    EXIT_GENERIC,
    EXIT_LOGIN,
    EXIT_OK,
    EXIT_USAGE,
    BiliError,
    LoginExpired,
    LoginRequired,
    NetworkError,
    NoSubtitle,
    RateLimited,
    VideoNotFound,
    redact,
)


class TestExceptionHierarchy:
    def test_all_subclass_bilierror(self):
        for cls in (
            LoginRequired,
            LoginExpired,
            NoSubtitle,
            VideoNotFound,
            RateLimited,
            NetworkError,
        ):
            assert issubclass(cls, BiliError)

    def test_bilierror_is_exception(self):
        assert issubclass(BiliError, Exception)


class TestExitCodes:
    def test_values(self):
        assert EXIT_OK == 0
        assert EXIT_GENERIC == 1
        assert EXIT_USAGE == 2
        assert EXIT_LOGIN == 3


class TestRedact:
    def test_long_secret_keeps_head_and_tail(self):
        assert redact("abcdefghijklmnop") == "abcd***mnop"

    def test_short_secret_fully_masked(self):
        assert redact("abc") == "***"

    def test_empty_secret(self):
        assert redact("") == "***"

    def test_threshold_boundary(self):
        # len == keep_head + keep_tail + 3 == 11 → fully masked
        assert redact("abcdefghijk") == "***"
        # len == 12 → partially shown
        assert redact("abcdefghijkl") == "abcd***ijkl"
