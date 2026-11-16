"""VTT to TXT converter module."""

import html
import json
import re

from vtt2txt.errors import BiliError

# Regex pattern to match timestamp lines in VTT format.
# Accepts the variants the WebVTT spec allows:
#   - hours segment optional:      00:01.140 --> 00:02.980
#   - '.' or ',' as ms separator:  00:00:01,140 --> 00:00:02,980
#   - trailing cue settings:       00:00:00.100 --> 00:00:01.140 align:start position:0%
TIMESTAMP_PATTERN = re.compile(
    r"^\d{2,}:\d{2}(?::\d{2})?[.,]\d{3}"
    r"\s*-->\s*"
    r"\d{2,}:\d{2}(?::\d{2})?[.,]\d{3}"
    r"(?:\s+.*)?$"
)

# Block types defined by the WebVTT spec that never carry cue text.
NON_CUE_PREFIXES = ("NOTE", "STYLE", "REGION")

# Inline cue markup: <i>, <b>, <u>, <ruby>, <c.classname>, <v Speaker>,
# and inline timestamps such as <00:00:01.000>.
INLINE_TAG_PATTERN = re.compile(r"<[^>]*>")


def _clean_line(line: str) -> str:
    """Strip inline markup and decode HTML entities from a subtitle line."""
    return html.unescape(INLINE_TAG_PATTERN.sub("", line)).replace("\u200b", "").strip()


def convert_vtt(content: str) -> str:
    """Convert VTT subtitle content to plain text.

    Cues are delimited by blank lines as the WebVTT spec requires, with an
    additional split on timestamp lines so that files which omit the blank
    separator are still handled. Cue identifiers, WEBVTT header metadata,
    NOTE/STYLE/REGION blocks, inline markup and HTML entities are all dropped.

    Args:
        content: The VTT file content as a string.

    Returns:
        Plain text with subtitle blocks joined by newlines.
        Returns empty string if no subtitles found.
    """
    # Normalise line endings and drop a UTF-8 BOM if present.
    normalized = content.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")

    subtitle_blocks = []

    for raw_block in re.split(r"\n\s*\n", normalized):
        lines = [line.strip() for line in raw_block.split("\n") if line.strip()]
        if not lines:
            continue

        # Skip WEBVTT header (optionally followed by a description on the same line).
        if lines[0].startswith("WEBVTT"):
            lines = lines[1:]
        if not lines:
            continue

        # NOTE / STYLE / REGION blocks never contain subtitle text.
        if lines[0].startswith(NON_CUE_PREFIXES):
            continue

        current_block_lines = []
        in_cue = False

        for line in lines:
            # A timestamp starts a new cue: flush the text collected so far.
            if TIMESTAMP_PATTERN.match(line):
                if current_block_lines:
                    subtitle_blocks.append("\n".join(current_block_lines))
                    current_block_lines = []
                in_cue = True
                continue

            # Anything before the first timestamp in a block is header metadata
            # (Kind:, Language:, ...) or a cue identifier, never subtitle text.
            if not in_cue:
                continue

            cleaned = _clean_line(line)
            if cleaned:
                current_block_lines.append(cleaned)

        if current_block_lines:
            subtitle_blocks.append("\n".join(current_block_lines))

    return "\n".join(subtitle_blocks)


def convert_bili_json(content: str) -> str:
    """Convert a Bilibili subtitle JSON string to plain text.

    The expected structure is ``{"body": [{"from": 0.0, "to": 1.14,
    "content": "文本"}, ...]}``.  Both ``content`` and ``text`` keys are
    tried (the field name may vary).  Inline markup and HTML entities are
    stripped via the shared :func:`_clean_line` primitive, and the output
    rules (single ``\\n`` join, no trailing newline) match
    :func:`convert_vtt`.

    Raises :class:`~vtt2txt.errors.BiliError` if the JSON is unparseable
    or if ``body`` is non-empty but every element lacks a recognised text
    field (field-drift protection).
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise BiliError(f"字幕 JSON 解析失败: {e}") from e

    body = data.get("body") if isinstance(data, dict) else None
    if not isinstance(body, list):
        return ""

    blocks: list[str] = []
    dict_items = 0
    missing_text = 0

    for item in body:
        if not isinstance(item, dict):
            continue
        dict_items += 1
        raw = item.get("content")
        if raw is None:
            raw = item.get("text")
        if raw is None:
            missing_text += 1
            continue
        if not isinstance(raw, str):
            raw = str(raw)
        cleaned = _clean_line(raw)
        if cleaned:
            blocks.append(cleaned)

    # Field-drift guard: body has dict items but none yielded text.
    if not blocks and dict_items > 0 and missing_text == dict_items:
        raise BiliError(
            "字幕 body 字段无法识别（所有元素均无 content/text 键）"
        )

    return "\n".join(blocks)
