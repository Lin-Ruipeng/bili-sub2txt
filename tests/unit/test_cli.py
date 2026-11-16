"""Tests for the CLI entry point."""

import sys

import pytest

from vtt2txt.cli import main


def run_main(monkeypatch, *argv):
    """Invoke main() with a fake argv, returning its exit code."""
    monkeypatch.setattr(sys, "argv", ["vtt2txt", *argv])
    return main()


class TestConversionOutcome:
    """Exit codes and empty-result handling."""

    def test_successful_conversion_returns_zero(self, tmp_path, monkeypatch, capsys):
        """A regular file converts and exits with 0."""
        input_dir = tmp_path / "source_vtt"
        output_dir = tmp_path / "target_txt"
        input_dir.mkdir()
        (input_dir / "a.vtt").write_text(
            "WEBVTT\n\n00:00:00.100 --> 00:00:01.140\n字幕内容", encoding="utf-8"
        )

        exit_code = run_main(monkeypatch, str(input_dir), str(output_dir))

        assert exit_code == 0
        assert (output_dir / "a.txt").read_text(encoding="utf-8") == "字幕内容"
        assert "1 succeeded, 0 failed" in capsys.readouterr().out

    def test_unparseable_file_is_reported_as_failure(self, tmp_path, monkeypatch, capsys):
        """A file with cue timestamps but no extracted text must fail loudly.

        This is the regression that used to write a 0-byte file and report
        success, leaving the user with no signal at all.
        """
        input_dir = tmp_path / "source_vtt"
        output_dir = tmp_path / "target_txt"
        input_dir.mkdir()
        # Contains '-->' but no timestamp matches the accepted format.
        (input_dir / "bad.vtt").write_text(
            "WEBVTT\n\n00:00:00.100 --> 00:00:01\n无法解析的时间戳", encoding="utf-8"
        )

        exit_code = run_main(monkeypatch, str(input_dir), str(output_dir))

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "found cue timestamps but extracted no text" in captured.err
        assert "1 succeeded, 0 failed" not in captured.out
        assert not (output_dir / "bad.txt").exists()

    def test_file_without_subtitles_only_warns(self, tmp_path, monkeypatch, capsys):
        """An empty VTT file is not a failure: it simply has no subtitle text."""
        input_dir = tmp_path / "source_vtt"
        output_dir = tmp_path / "target_txt"
        input_dir.mkdir()
        (input_dir / "empty.vtt").write_text("WEBVTT\n\n", encoding="utf-8")
        (input_dir / "ok.vtt").write_text(
            "WEBVTT\n\n00:00:00.100 --> 00:00:01.140\n内容", encoding="utf-8"
        )

        exit_code = run_main(monkeypatch, str(input_dir), str(output_dir))

        captured = capsys.readouterr()
        assert exit_code == 0
        assert "no subtitle text found in file" in captured.err
        assert not (output_dir / "empty.txt").exists()
        assert (output_dir / "ok.txt").read_text(encoding="utf-8") == "内容"

    def test_batch_continues_after_a_failure(self, tmp_path, monkeypatch, capsys):
        """One bad file must not abort the remaining conversions."""
        input_dir = tmp_path / "source_vtt"
        output_dir = tmp_path / "target_txt"
        input_dir.mkdir()
        (input_dir / "bad.vtt").write_text(
            "WEBVTT\n\n00:00:00.100 --> 00:00:01\n坏的", encoding="utf-8"
        )
        (input_dir / "good.vtt").write_text(
            "WEBVTT\n\n00:00:00.100 --> 00:00:01.140\n好的", encoding="utf-8"
        )

        exit_code = run_main(monkeypatch, str(input_dir), str(output_dir))

        assert exit_code == 1
        assert (output_dir / "good.txt").read_text(encoding="utf-8") == "好的"
        assert "1 succeeded, 1 failed" in capsys.readouterr().out

    def test_nested_structure_is_preserved(self, tmp_path, monkeypatch):
        """Output mirrors the input directory layout."""
        input_dir = tmp_path / "source_vtt"
        output_dir = tmp_path / "target_txt"
        nested = input_dir / "sub" / "deep"
        nested.mkdir(parents=True)
        (nested / "a.vtt").write_text(
            "WEBVTT\n\n00:00:00.100 --> 00:00:01.140\n嵌套", encoding="utf-8"
        )

        assert run_main(monkeypatch, str(input_dir), str(output_dir)) == 0
        assert (output_dir / "sub" / "deep" / "a.txt").read_text(encoding="utf-8") == "嵌套"


class TestArgumentValidation:
    """Usage errors must exit non-zero."""

    def test_wrong_argument_count(self, monkeypatch, capsys):
        assert run_main(monkeypatch, "only-one-arg") == 1
        assert "Usage:" in capsys.readouterr().err

    def test_missing_input_directory(self, tmp_path, monkeypatch, capsys):
        missing = tmp_path / "does-not-exist"
        exit_code = run_main(monkeypatch, str(missing), str(tmp_path / "out"))
        assert exit_code == 1
        assert "does not exist" in capsys.readouterr().err

    def test_input_path_is_a_file(self, tmp_path, monkeypatch, capsys):
        a_file = tmp_path / "a.vtt"
        a_file.write_text("WEBVTT\n", encoding="utf-8")
        exit_code = run_main(monkeypatch, str(a_file), str(tmp_path / "out"))
        assert exit_code == 1
        assert "not a directory" in capsys.readouterr().err

    def test_no_vtt_files_found(self, tmp_path, monkeypatch, capsys):
        input_dir = tmp_path / "source_vtt"
        input_dir.mkdir()
        (input_dir / "note.txt").write_text("hello", encoding="utf-8")
        exit_code = run_main(monkeypatch, str(input_dir), str(tmp_path / "out"))
        assert exit_code == 1
        assert "No .vtt files found" in capsys.readouterr().err
