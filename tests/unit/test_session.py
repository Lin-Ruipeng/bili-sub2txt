"""Tests for session persistence."""

import json
import sys

import pytest

from bili_sub2txt.bilibili.session import (
    clear_session,
    get_sessdata,
    load_session,
    save_session,
    session_path,
)


class TestSession:
    def test_load_nonexistent(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BILI_SUB2TXT_SESSION_DIR", str(tmp_path))
        assert load_session() == {}

    def test_save_load_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BILI_SUB2TXT_SESSION_DIR", str(tmp_path))
        save_session("my_secret_sessdata")
        assert load_session() == {"SESSDATA": "my_secret_sessdata"}

    def test_get_sessdata(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BILI_SUB2TXT_SESSION_DIR", str(tmp_path))
        assert get_sessdata() is None
        save_session("abc123def456")
        assert get_sessdata() == "abc123def456"

    def test_clear(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BILI_SUB2TXT_SESSION_DIR", str(tmp_path))
        save_session("abc")
        assert session_path().exists()
        clear_session()
        assert not session_path().exists()
        assert load_session() == {}

    def test_env_override_path(self, tmp_path, monkeypatch):
        custom = tmp_path / "custom_session_dir"
        monkeypatch.setenv("BILI_SUB2TXT_SESSION_DIR", str(custom))
        save_session("xyz")
        assert session_path() == custom / "session.json"


class TestDpapiProtection:
    """Issue #7 (P4): DPAPI-encrypt session.json on Windows."""

    @pytest.mark.skipif(sys.platform != "win32", reason="DPAPI is Windows-only")
    def test_save_encrypts_and_roundtrips(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BILI_SUB2TXT_SESSION_DIR", str(tmp_path))
        save_session("my_secret_sessdata")

        raw = session_path().read_text(encoding="utf-8")
        stored = json.loads(raw)
        # Encrypted envelope, not plaintext.
        assert stored.get("scheme") == "dpapi"
        assert "my_secret_sessdata" not in raw
        # Transparent decrypt on read.
        assert get_sessdata() == "my_secret_sessdata"

    def test_dpapi_unavailable_falls_back_to_plaintext(
        self, tmp_path, monkeypatch, capsys
    ):
        monkeypatch.setenv("BILI_SUB2TXT_SESSION_DIR", str(tmp_path))
        monkeypatch.setattr(
            "bili_sub2txt.bilibili.session._dpapi_protect", lambda data: None
        )
        monkeypatch.setattr(sys, "platform", "win32")

        save_session("plaintext_fallback_sessdata")

        stored = json.loads(session_path().read_text(encoding="utf-8"))
        assert stored == {"SESSDATA": "plaintext_fallback_sessdata"}
        assert "明文保存" in capsys.readouterr().err

    def test_decrypt_failure_returns_empty_with_warning(
        self, tmp_path, monkeypatch, capsys
    ):
        monkeypatch.setenv("BILI_SUB2TXT_SESSION_DIR", str(tmp_path))
        monkeypatch.setattr(
            "bili_sub2txt.bilibili.session._dpapi_unprotect", lambda blob: None
        )
        (tmp_path / "session.json").write_text(
            json.dumps({"scheme": "dpapi", "data": "not-a-valid-blob"}),
            encoding="utf-8",
        )

        assert load_session() == {}
        assert "解密失败" in capsys.readouterr().err
        assert get_sessdata() is None

    def test_legacy_plaintext_file_is_read_transparently(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("BILI_SUB2TXT_SESSION_DIR", str(tmp_path))
        (tmp_path / "session.json").write_text(
            json.dumps({"SESSDATA": "legacy_plaintext_sessdata"}),
            encoding="utf-8",
        )
        assert load_session() == {"SESSDATA": "legacy_plaintext_sessdata"}
        assert get_sessdata() == "legacy_plaintext_sessdata"
