"""Tests for filename sanitisation and output-path construction."""

from pathlib import Path

from bili_sub2txt.naming import build_output_path, sanitize_filename


class TestSanitizeFilename:
    def test_illegal_characters_replaced(self):
        assert sanitize_filename("a/b:c*d?e") == "a_b_c_d_e"

    def test_reserved_name_gets_suffix(self):
        assert sanitize_filename("CON").endswith("_")
        assert sanitize_filename("nul").endswith("_")
        assert sanitize_filename("COM1").endswith("_")

    def test_truncation(self):
        name = "x" * 100
        assert len(sanitize_filename(name, max_len=80)) == 80

    def test_empty_falls_back(self):
        assert sanitize_filename("") == "untitled"
        assert sanitize_filename("///") == "untitled"

    def test_strips_trailing_dots_and_spaces(self):
        assert sanitize_filename("title.  ") == "title"
        assert sanitize_filename("title...") == "title"


class TestBuildOutputPath:
    def test_single_part(self, tmp_path):
        p = build_output_path(tmp_path, "BV1xx", "序论", None, 1)
        assert p == tmp_path / "BV1xx" / "序论.txt"

    def test_multi_part(self, tmp_path):
        p = build_output_path(tmp_path, "BV1xx", "第二集", 2, 3)
        assert p == tmp_path / "BV1xx" / "02_第二集.txt"

    def test_illegal_title_sanitised(self, tmp_path):
        p = build_output_path(tmp_path, "BV1xx", "a:b/c?", 1, 1)
        assert p.name == "a_b_c_.txt"
