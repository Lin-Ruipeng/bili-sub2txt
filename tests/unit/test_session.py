"""Tests for session persistence."""

from vtt2txt.bilibili.session import (
    clear_session,
    get_sessdata,
    load_session,
    save_session,
    session_path,
)


class TestSession:
    def test_load_nonexistent(self, tmp_path, monkeypatch):
        monkeypatch.setenv("VTT2TXT_SESSION_DIR", str(tmp_path))
        assert load_session() == {}

    def test_save_load_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.setenv("VTT2TXT_SESSION_DIR", str(tmp_path))
        save_session("my_secret_sessdata")
        assert load_session() == {"SESSDATA": "my_secret_sessdata"}

    def test_get_sessdata(self, tmp_path, monkeypatch):
        monkeypatch.setenv("VTT2TXT_SESSION_DIR", str(tmp_path))
        assert get_sessdata() is None
        save_session("abc123def456")
        assert get_sessdata() == "abc123def456"

    def test_clear(self, tmp_path, monkeypatch):
        monkeypatch.setenv("VTT2TXT_SESSION_DIR", str(tmp_path))
        save_session("abc")
        assert session_path().exists()
        clear_session()
        assert not session_path().exists()
        assert load_session() == {}

    def test_env_override_path(self, tmp_path, monkeypatch):
        custom = tmp_path / "custom_session_dir"
        monkeypatch.setenv("VTT2TXT_SESSION_DIR", str(custom))
        save_session("xyz")
        assert session_path() == custom / "session.json"
