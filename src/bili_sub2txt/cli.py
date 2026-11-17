"""CLI for bili_sub2txt — convert VTT files or fetch Bilibili subtitles."""

import argparse
import sys
from pathlib import Path

from bili_sub2txt import __version__
from bili_sub2txt.bilibili import auth, fetcher
from bili_sub2txt.bilibili.session import get_sessdata
from bili_sub2txt.converter import convert_vtt
from bili_sub2txt.errors import EXIT_GENERIC, EXIT_LOGIN, EXIT_OK, LoginExpired
from bili_sub2txt.path_mapper import map_path


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="bili_sub2txt",
        description="将 VTT 字幕文件转换为纯文本,或从 Bilibili 下载字幕。",
    )
    parser.add_argument(
        "-V", "--version", action="version", version=f"%(prog)s {__version__}"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # convert — existing local-file conversion.
    p_convert = sub.add_parser("convert", help="转换本地 VTT 文件目录")
    p_convert.add_argument("input_dir", type=Path, help="含 .vtt 文件的输入目录")
    p_convert.add_argument("output_dir", type=Path, help="TXT 输出目录")

    # fetch — download subtitles from Bilibili.
    p_fetch = sub.add_parser("fetch", help="通过 BV 号下载字幕并转换为 TXT")
    p_fetch.add_argument("target", help="BV 号或视频链接")
    p_fetch.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("target_txt"),
        help="输出目录（默认 target_txt/）",
    )
    p_fetch.add_argument("--lang", default=None, help="指定字幕语言（如 zh-Hans）")

    # login — QR-code login.
    sub.add_parser("login", help="扫码登录 B 站")

    return parser


def cmd_convert(input_dir: Path, output_dir: Path) -> int:
    """Convert all VTT files under *input_dir* into TXT files under *output_dir*."""
    if not input_dir.exists():
        print(f"Error: Input directory does not exist: {input_dir}", file=sys.stderr)
        return EXIT_GENERIC

    if not input_dir.is_dir():
        print(f"Error: Input path is not a directory: {input_dir}", file=sys.stderr)
        return EXIT_GENERIC

    vtt_files = list(input_dir.rglob("*.vtt"))

    if not vtt_files:
        print(f"No .vtt files found in {input_dir}", file=sys.stderr)
        return EXIT_GENERIC

    print(f"Found {len(vtt_files)} VTT file(s) to convert")

    success_count = 0
    error_count = 0

    for vtt_file in vtt_files:
        print(f"Processing: {vtt_file.relative_to(input_dir)}")

        try:
            content = vtt_file.read_text(encoding="utf-8")
            converted = convert_vtt(content)

            if not converted.strip():
                if "-->" in content:
                    print(
                        f"  Warning: found cue timestamps but extracted no text: {vtt_file}",
                        file=sys.stderr,
                    )
                    error_count += 1
                else:
                    print(
                        f"  Warning: no subtitle text found in file: {vtt_file}",
                        file=sys.stderr,
                    )
                continue

            output_path = map_path(vtt_file, input_dir, output_dir)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(converted, encoding="utf-8")
            success_count += 1

        except FileNotFoundError:
            print(f"  Error: File not found: {vtt_file}", file=sys.stderr)
            error_count += 1
        except PermissionError:
            print(f"  Error: Permission denied: {vtt_file}", file=sys.stderr)
            error_count += 1
        except Exception as e:
            print(f"  Error: Failed to convert {vtt_file}: {e}", file=sys.stderr)
            error_count += 1

    print(f"\nConversion complete: {success_count} succeeded, {error_count} failed")
    return EXIT_GENERIC if error_count > 0 else EXIT_OK


def cmd_fetch(target: str, output_dir: Path, lang: str | None) -> int:
    """Download subtitles for *target* and convert to TXT."""
    sessdata = get_sessdata()
    return fetcher.fetch(
        target, output_dir=output_dir, lang=lang, sessdata=sessdata
    )


def cmd_login() -> int:
    """Run QR-code login and persist the session."""
    try:
        auth.login()
        return EXIT_OK
    except LoginExpired as e:
        print(f"登录失败: {e}", file=sys.stderr)
        return EXIT_GENERIC
    except Exception as e:
        print(f"登录失败: {e}", file=sys.stderr)
        return EXIT_GENERIC


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point.

    Args:
        argv: argument list excluding the program name. When ``None``,
            ``sys.argv[1:]`` is used.

    Returns:
        Exit code (0 success, 1 generic error, 2 usage error, 3 login required).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "convert":
        return cmd_convert(args.input_dir, args.output_dir)
    if args.command == "fetch":
        return cmd_fetch(args.target, args.output, args.lang)
    if args.command == "login":
        return cmd_login()

    return 2  # Unreachable (subparsers required=True).


if __name__ == "__main__":
    sys.exit(main())
