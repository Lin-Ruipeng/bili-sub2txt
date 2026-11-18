"""Fetch orchestration: download subtitles, convert, and write TXT files."""

import json
import sys
from pathlib import Path

from bili_sub2txt.bilibili.api import fetch_subtitle_json, parse_target
from bili_sub2txt.bilibili.net import Transport, default_transport
from bili_sub2txt.converter import convert_bili_json
from bili_sub2txt.errors import (
    EXIT_GENERIC,
    EXIT_LOGIN,
    EXIT_OK,
    BiliError,
    LoginExpired,
    NetworkError,
    NoSubtitle,
    VideoNotFound,
)
from bili_sub2txt.naming import build_output_path


def _cross_check_duration(json_text: str, expected_duration: int) -> bool:
    """Return ``True`` if the subtitle's last ``to`` is within 0.5–1.25× of *expected*.

    A mismatch does **not** abort the write — it is only a warning signal
    that the subtitle may belong to a different video (the known failure
    mode of unsigned WBI requests).  Returns ``True`` (pass) when there is
    no reference duration or the JSON cannot be parsed.
    """
    if not expected_duration:
        return True
    try:
        data = json.loads(json_text)
        body = data.get("body", [])
        if not body:
            return True
        last_to = max(
            (item.get("to", 0) for item in body if isinstance(item, dict)),
            default=0,
        )
    except Exception:
        return True
    ratio = last_to / expected_duration
    return 0.5 <= ratio <= 1.25


def fetch(
    target: str,
    *,
    output_dir: Path,
    lang: str | None = None,
    transport: Transport | None = None,
    sessdata: str | None = None,
    debug: bool = False,
) -> int:
    """Download subtitles for *target* (BV or URL) and write TXT files.

    Returns one of ``EXIT_OK`` / ``EXIT_GENERIC`` / ``EXIT_LOGIN``.
    """
    try:
        bvid = parse_target(target)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_GENERIC

    t = transport or default_transport()

    # Fetch all subtitle JSON.
    try:
        info, subtitles = fetch_subtitle_json(t, sessdata, bvid, lang=lang)
    except LoginExpired:
        print("登录态失效,请运行 bili_sub2txt login 重新登录。", file=sys.stderr)
        return EXIT_LOGIN
    except NoSubtitle as e:
        if not sessdata:
            print("需要登录才能下载字幕,请先运行 bili_sub2txt login。", file=sys.stderr)
            return EXIT_LOGIN
        print(f"下载失败: {e}", file=sys.stderr)
        return EXIT_GENERIC
    except VideoNotFound as e:
        print(f"视频不存在: {e}", file=sys.stderr)
        return EXIT_GENERIC
    except NetworkError as e:
        print(f"网络错误: {e}", file=sys.stderr)
        return EXIT_GENERIC

    total_pages = len(info.pages) or 1
    success_count = 0
    error_count = 0

    print(f"视频: {info.title}  分 P: {total_pages}")

    for sub in subtitles:
        label = sub.part_title or f"P{sub.page_index}"
        try:
            txt = convert_bili_json(sub.json_text)
            if not txt.strip():
                print(f"  Warning: 字幕内容为空: {label}", file=sys.stderr)
                error_count += 1
                continue

            output_path = build_output_path(
                output_dir, bvid, sub.part_title, sub.page_index, total_pages
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(txt, encoding="utf-8")

            # Duration cross-check (warning only, never blocks the write).
            if not _cross_check_duration(sub.json_text, info.duration):
                print(
                    f"  Warning: 字幕时长与视频时长差异较大,可能字幕来源不一致: {label}",
                    file=sys.stderr,
                )

            print(f"  已保存: {output_path}")
            success_count += 1

        except BiliError as e:
            print(f"  Error: 转换失败 {label}: {e}", file=sys.stderr)
            error_count += 1
        except Exception as e:
            print(f"  Error: 处理失败 {label}: {e}", file=sys.stderr)
            error_count += 1

    print(
        f"\n下载完成: {success_count} succeeded, {error_count} failed",
        file=sys.stderr if success_count == 0 else None,
    )

    if success_count == 0:
        return EXIT_GENERIC
    return EXIT_GENERIC if error_count > 0 else EXIT_OK
