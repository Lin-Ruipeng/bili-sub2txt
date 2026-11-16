"""Login-session persistence for SESSDATA.

The session file is stored at:
  - ``$VTT2TXT_SESSION_DIR/session.json`` (if the env var is set — for tests)
  - ``%APPDATA%/vtt2txt/session.json`` on Windows
  - ``~/.config/vtt2txt/session.json`` elsewhere

Only ``SESSDATA`` is persisted; other cookies (``bili_jct``, etc.) are
intentionally discarded to minimise the sensitive-data footprint.
"""

import json
import os
import sys
from pathlib import Path

SESSION_DIR_ENV = "VTT2TXT_SESSION_DIR"
SESSION_FILENAME = "session.json"


def session_path() -> Path:
    """Return the path to the session file."""
    env_dir = os.environ.get(SESSION_DIR_ENV)
    if env_dir:
        return Path(env_dir) / SESSION_FILENAME

    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "vtt2txt" / SESSION_FILENAME

    return Path.home() / ".config" / "vtt2txt" / SESSION_FILENAME


def load_session() -> dict[str, str]:
    """Load the session file, returning ``{}`` if absent or corrupted."""
    p = session_path()
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def save_session(sessdata: str) -> None:
    """Persist *sessdata* to the session file with best-effort ``0600`` perms."""
    p = session_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"SESSDATA": sessdata}, indent=2),
        encoding="utf-8",
    )
    try:
        os.chmod(p, 0o600)
    except OSError:
        # Windows has limited chmod support; document but don't fail.
        pass


def get_sessdata() -> str | None:
    """Return the stored SESSDATA, or ``None`` if not logged in."""
    return load_session().get("SESSDATA")


def clear_session() -> None:
    """Delete the session file if it exists."""
    p = session_path()
    if p.exists():
        try:
            p.unlink()
        except OSError:
            pass
