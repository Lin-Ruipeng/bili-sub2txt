"""Filename sanitisation and output-path construction for fetched subtitles."""

import re
from pathlib import Path

# Characters forbidden in Windows filenames (also cleaned for cross-platform safety).
_WIN_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Windows reserved names that cannot appear as a file stem.
_WIN_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)


def sanitize_filename(name: str, max_len: int = 80) -> str:
    """Replace illegal characters, strip dots/spaces, and truncate.

    Empty or all-illegal names fall back to ``"untitled"``.
    """
    cleaned = _WIN_ILLEGAL.sub("_", name).strip().rstrip(".")
    if not cleaned.strip("_"):
        return "untitled"
    # Avoid Windows reserved names (CON, PRN, …) by appending an underscore.
    stem = cleaned.split(".")[0] if "." in cleaned else cleaned
    if stem.upper() in _WIN_RESERVED:
        cleaned += "_"
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len]
    return cleaned


def build_output_path(
    output_dir: Path,
    bvid: str,
    title: str,
    page_index: int | None,
    total_pages: int,
) -> Path:
    """Build the output ``.txt`` path for a single subtitle.

    - Single-part video: ``<output_dir>/<bvid>/<title>.txt``
    - Multi-part video:  ``<output_dir>/<bvid>/<page:02d>_<title>.txt``
    """
    safe_title = sanitize_filename(title)
    base = output_dir / bvid
    if total_pages > 1 and page_index is not None:
        return base / f"{page_index:02d}_{safe_title}.txt"
    return base / f"{safe_title}.txt"
