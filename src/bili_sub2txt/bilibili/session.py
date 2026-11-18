"""Login-session persistence for SESSDATA.

The session file is stored at:
  - ``$BILI_SUB2TXT_SESSION_DIR/session.json`` (if the env var is set — for tests)
  - ``%APPDATA%/bili-sub2txt/session.json`` on Windows
  - ``~/.config/bili-sub2txt/session.json`` elsewhere

Only ``SESSDATA`` is persisted; other cookies (``bili_jct``, etc.) are
intentionally discarded to minimise the sensitive-data footprint.

On Windows the payload is encrypted with DPAPI (``CryptProtectData``) —
bound to the current user and machine, so a copied/stolen ``session.json``
cannot be decrypted elsewhere.  The file then has the shape
``{"scheme": "dpapi", "data": "<base64>"}``.  Earlier versions wrote the
plaintext ``{"SESSDATA": "..."}`` shape, which is still read transparently
(no re-login needed after upgrading).  If DPAPI is unavailable the file
falls back to plaintext with a warning.
"""

import base64
import json
import os
import sys
from pathlib import Path

SESSION_DIR_ENV = "BILI_SUB2TXT_SESSION_DIR"
SESSION_FILENAME = "session.json"
SCHEME_DPAPI = "dpapi"


def session_path() -> Path:
    """Return the path to the session file."""
    env_dir = os.environ.get(SESSION_DIR_ENV)
    if env_dir:
        return Path(env_dir) / SESSION_FILENAME

    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "bili-sub2txt" / SESSION_FILENAME

    return Path.home() / ".config" / "bili-sub2txt" / SESSION_FILENAME


# ---------------------------------------------------------------------------
# DPAPI helpers (Windows only; ctypes, no third-party dependencies).
#

def _dpapi_protect(data: bytes) -> str | None:
    """Encrypt *data* with DPAPI; return base64 text, or ``None`` on failure."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        import ctypes.wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [
                ("cbData", ctypes.wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_char)),
            ]

        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32

        buf = ctypes.create_string_buffer(data, len(data))
        blob_in = DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
        blob_out = DATA_BLOB()
        ok = crypt32.CryptProtectData(
            ctypes.byref(blob_in),
            None,           # szDataDescr
            None,           # pOptionalEntropy
            None,           # pvReserved
            None,           # pPromptStruct
            0,              # dwFlags
            ctypes.byref(blob_out),
        )
        if not ok:
            return None
        try:
            raw = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            kernel32.LocalFree(blob_out.pbData)
        return base64.b64encode(raw).decode("ascii")
    except Exception:
        return None


def _dpapi_unprotect(blob_b64: str) -> bytes | None:
    """Decrypt a base64 DPAPI blob; return bytes, or ``None`` on failure."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        import ctypes.wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [
                ("cbData", ctypes.wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_char)),
            ]

        data = base64.b64decode(blob_b64)

        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32

        buf = ctypes.create_string_buffer(data, len(data))
        blob_in = DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
        blob_out = DATA_BLOB()
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(blob_in),
            None,           # pDataDescr
            None,           # pOptionalEntropy
            None,           # pvReserved
            None,           # pPromptStruct
            0,              # dwFlags
            ctypes.byref(blob_out),
        )
        if not ok:
            return None
        try:
            return ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            kernel32.LocalFree(blob_out.pbData)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Session file I/O.
#

def load_session() -> dict[str, str]:
    """Load the session file, returning ``{}`` if absent or corrupted.

    Legacy plaintext files are read transparently.  A DPAPI-encrypted
    file that cannot be decrypted (e.g. copied from another machine)
    is reported to stderr and treated as not logged in, so downstream
    flows exit with the standard "login required" code.
    """
    p = session_path()
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}

    if data.get("scheme") == SCHEME_DPAPI:
        raw = _dpapi_unprotect(str(data.get("data", "")))
        if raw is None:
            print(
                "警告: session.json 解密失败(DPAPI),请重新运行 bili_sub2txt login。",
                file=sys.stderr,
            )
            return {}
        try:
            return {"SESSDATA": raw.decode("utf-8")}
        except UnicodeDecodeError:
            return {}

    # Legacy plaintext format.
    return {str(k): str(v) for k, v in data.items() if k != "scheme"}


def save_session(sessdata: str) -> None:
    """Persist *sessdata* to the session file.

    On Windows the payload is DPAPI-encrypted (best effort: on failure the
    file falls back to plaintext with a stderr warning).  Elsewhere the
    file is written with best-effort ``0600`` permissions.
    """
    p = session_path()
    p.parent.mkdir(parents=True, exist_ok=True)

    if sys.platform == "win32":
        blob_b64 = _dpapi_protect(sessdata.encode("utf-8"))
        if blob_b64 is not None:
            p.write_text(
                json.dumps({"scheme": SCHEME_DPAPI, "data": blob_b64}, indent=2),
                encoding="utf-8",
            )
            return
        print(
            "警告: DPAPI 加密不可用,session.json 将以明文保存。",
            file=sys.stderr,
        )

    p.write_text(
        json.dumps({"SESSDATA": sessdata}, indent=2),
        encoding="utf-8",
    )
    try:
        os.chmod(p, 0o600)
    except OSError:
        # Some filesystems have limited chmod support; document but don't fail.
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
