"""Regression tests for the `python -m vtt2txt` entry point exit code.

These spawn a real subprocess because the bug is specifically about the
entry script discarding main()'s return value — only an actual
`python -m vtt2txt` invocation exercises that path.
"""

import os
import subprocess
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
ENV = {**os.environ, "PYTHONPATH": str(SRC_DIR)}


def _run(*args: str, cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "vtt2txt", *args],
        cwd=cwd,
        env=ENV,
        capture_output=True,
        text=True,
        timeout=30,
    )


class TestMainModuleExitCode:
    def test_success_returns_zero(self, tmp_path):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        (input_dir / "a.vtt").write_text(
            "WEBVTT\n\n00:00:00.100 --> 00:00:01.140\n字幕",
            encoding="utf-8",
        )
        result = _run("convert", str(input_dir), str(tmp_path / "out"), cwd=str(tmp_path))
        assert result.returncode == 0
        assert (tmp_path / "out" / "a.txt").exists()

    def test_missing_input_dir_returns_nonzero(self, tmp_path):
        result = _run("convert", str(tmp_path / "nope"), str(tmp_path / "out"), cwd=str(tmp_path))
        assert result.returncode != 0
        assert "does not exist" in result.stderr
