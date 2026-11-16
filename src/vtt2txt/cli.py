"""CLI for vtt2txt - Convert VTT subtitle files to plain text."""

import argparse
import sys
from pathlib import Path

from vtt2txt import __version__
from vtt2txt.converter import convert_vtt
from vtt2txt.path_mapper import map_path


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="vtt2txt",
        description="将 VTT 字幕文件转换为纯文本。",
    )
    parser.add_argument(
        "-V", "--version", action="version", version=f"%(prog)s {__version__}"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_convert = sub.add_parser("convert", help="转换本地 VTT 文件目录")
    p_convert.add_argument("input_dir", type=Path, help="含 .vtt 文件的输入目录")
    p_convert.add_argument("output_dir", type=Path, help="TXT 输出目录")

    p_fetch = sub.add_parser("fetch", help="通过 BV 号下载字幕（后续版本提供）")
    p_fetch.add_argument(
        "target", nargs="?", help="BV 号或视频链接（后续版本启用）"
    )

    sub.add_parser("login", help="扫码登录 B 站（后续版本提供）")

    return parser


def cmd_convert(input_dir: Path, output_dir: Path) -> int:
    """Convert all VTT files under *input_dir* into TXT files under *output_dir*.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Validate input directory
    if not input_dir.exists():
        print(f"Error: Input directory does not exist: {input_dir}", file=sys.stderr)
        return 1

    if not input_dir.is_dir():
        print(f"Error: Input path is not a directory: {input_dir}", file=sys.stderr)
        return 1

    # Find all VTT files recursively
    vtt_files = list(input_dir.rglob("*.vtt"))

    if not vtt_files:
        print(f"No .vtt files found in {input_dir}", file=sys.stderr)
        return 1

    print(f"Found {len(vtt_files)} VTT file(s) to convert")

    success_count = 0
    error_count = 0

    for vtt_file in vtt_files:
        print(f"Processing: {vtt_file.relative_to(input_dir)}")

        try:
            # Read VTT file
            content = vtt_file.read_text(encoding="utf-8")

            # Convert content
            converted = convert_vtt(content)

            # Never write an empty file and report it as a success. A file that
            # does contain cue timestamps but yields no text is treated as a
            # failure, so unsupported formats surface instead of failing silently.
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

            # Map output path
            output_path = map_path(vtt_file, input_dir, output_dir)

            # Create output directory if needed
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Write converted content
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

    return 1 if error_count > 0 else 0


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point.

    Args:
        argv: argument list excluding the program name. When ``None``,
            ``sys.argv[1:]`` is used.

    Returns:
        Exit code (0 for success, 1 for error, 2 for usage error).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "convert":
        return cmd_convert(args.input_dir, args.output_dir)

    # fetch / login are placeholders for a future release.
    print(
        f"vtt2txt {args.command}: 该功能将在后续版本提供。",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
