from bili_sub2txt.converter import convert_vtt


class TestConvertVtt:
    """Tests for convert_vtt function - RED phase of TDD."""

    def test_skip_webvtt_header(self):
        """WEBVTT header line should be skipped."""
        vtt = "WEBVTT\n\n00:00:00.100 --> 00:00:01.140\nText"
        result = convert_vtt(vtt)
        assert "WEBVTT" not in result

    def test_skip_timestamp_line(self):
        """Timestamp lines (00:00:00.100 --> 00:00:01.140) should be skipped."""
        vtt = "WEBVTT\n\n00:00:00.100 --> 00:00:01.140\nSubtitle text"
        result = convert_vtt(vtt)
        assert "-->" not in result
        assert "00:00:00.100" not in result

    def test_keep_subtitle_text(self):
        """Subtitle text lines should be kept."""
        vtt = "WEBVTT\n\n00:00:00.100 --> 00:00:01.140\n这是第一条字幕"
        result = convert_vtt(vtt)
        assert "这是第一条字幕" in result

    def test_multiple_subtitles_joined_by_newline(self):
        """Multiple subtitles should be joined by newlines."""
        vtt = """WEBVTT

00:00:00.100 --> 00:00:01.140
这是第一条字幕

00:00:01.140 --> 00:00:01.980
这是第二条字幕
"""
        result = convert_vtt(vtt)
        lines = result.strip().split("\n")
        assert len(lines) == 2
        assert lines[0] == "这是第一条字幕"
        assert lines[1] == "这是第二条字幕"

    def test_empty_lines_are_skipped(self):
        """Empty lines should not appear in output."""
        vtt = """WEBVTT

00:00:00.100 --> 00:00:01.140
Subtitle

00:00:01.140 --> 00:00:01.980
Another subtitle
"""
        result = convert_vtt(vtt)
        assert result != ""
        # Should not have consecutive newlines (empty lines)
        assert "\n\n" not in result

    def test_multiline_subtitle(self):
        """Subtitles spanning multiple lines should be kept as single unit."""
        vtt = """WEBVTT

00:00:00.100 --> 00:00:01.140
Line one of subtitle
Line two of subtitle

00:00:01.140 --> 00:00:01.980
Second subtitle
"""
        result = convert_vtt(vtt)
        # Multiline subtitle blocks are preserved with internal newlines
        assert "Line one of subtitle\nLine two of subtitle" in result
        assert "Second subtitle" in result
        # Count subtitle blocks by counting timestamps (2 timestamps = 2 blocks)
        # We can verify by counting timestamp matches in the original
        assert result.count("Line one") == 1
        assert result.count("Second subtitle") == 1


class TestRealWorldVttFormats:
    """Regression tests for VTT variants produced by real-world tools.

    Each case used to be mishandled: cue settings and abbreviated timestamps
    produced an empty result, while identifiers and NOTE blocks leaked into
    the subtitle text.
    """

    def test_timestamp_with_cue_settings(self):
        """Cue settings after the timestamp must not break parsing."""
        vtt = "WEBVTT\n\n00:00:00.100 --> 00:00:01.140 align:start position:0%\n这是一条字幕"
        assert convert_vtt(vtt) == "这是一条字幕"

    def test_timestamp_without_hours_segment(self):
        """The hours segment is optional in the WebVTT spec."""
        vtt = "WEBVTT\n\n00:01.140 --> 00:02.980\nShort form timestamp"
        assert convert_vtt(vtt) == "Short form timestamp"

    def test_timestamp_with_comma_millisecond_separator(self):
        """Some exporters write a comma instead of a dot before milliseconds."""
        vtt = "WEBVTT\n\n00:00:01,140 --> 00:00:02,980\nComma separator"
        assert convert_vtt(vtt) == "Comma separator"

    def test_cue_identifier_is_dropped(self):
        """A cue identifier line must not become subtitle text."""
        vtt = (
            "WEBVTT\n\n"
            "00:00:00.100 --> 00:00:01.140\n第一条\n\n"
            "cue-2\n00:00:01.140 --> 00:00:01.980\n第二条"
        )
        assert convert_vtt(vtt) == "第一条\n第二条"

    def test_note_block_is_dropped(self):
        """NOTE blocks are comments, not subtitle text."""
        vtt = (
            "WEBVTT\n\n"
            "00:00:00.100 --> 00:00:01.140\n第一条\n\n"
            "NOTE 这是注释\n\n"
            "00:00:01.140 --> 00:00:01.980\n第二条"
        )
        assert convert_vtt(vtt) == "第一条\n第二条"

    def test_style_and_region_blocks_are_dropped(self):
        """STYLE and REGION blocks must be ignored entirely."""
        vtt = (
            "WEBVTT\n\n"
            "STYLE\n::cue { color: yellow }\n\n"
            "REGION\nid:fred width:40%\n\n"
            "00:00:00.100 --> 00:00:01.140\n正文"
        )
        assert convert_vtt(vtt) == "正文"

    def test_header_metadata_is_dropped(self):
        """Kind/Language header lines must not leak into the output."""
        vtt = "WEBVTT\nKind: captions\nLanguage: zh\n\n00:00:00.100 --> 00:00:01.140\n字幕内容"
        assert convert_vtt(vtt) == "字幕内容"

    def test_inline_markup_is_stripped(self):
        """Inline cue tags are not part of the plain text."""
        vtt = "WEBVTT\n\n00:00:00.100 --> 00:00:01.140\n<v Speaker>你好 <i>再见</i>"
        assert convert_vtt(vtt) == "你好 再见"

    def test_html_entities_are_decoded(self):
        """HTML entities must be decoded to their characters."""
        vtt = "WEBVTT\n\n00:00:00.100 --> 00:00:01.140\nA &amp; B &lt;C&gt; &nbsp;end"
        assert convert_vtt(vtt) == "A & B <C> \u00a0end"

    def test_cues_without_blank_line_separator(self):
        """Files that omit the blank separator between cues still work."""
        vtt = (
            "WEBVTT\n\n00:00:00.100 --> 00:00:01.140\n第一条\n00:00:01.140 --> 00:00:01.980\n第二条"
        )
        assert convert_vtt(vtt) == "第一条\n第二条"

    def test_crlf_line_endings(self):
        """Windows line endings must be handled."""
        vtt = "WEBVTT\r\n\r\n00:00:00.100 --> 00:00:01.140\r\nCRLF 内容\r\n"
        assert convert_vtt(vtt) == "CRLF 内容"

    def test_utf8_bom_is_ignored(self):
        """A leading UTF-8 BOM must not prevent header detection."""
        vtt = "\ufeffWEBVTT\n\n00:00:00.100 --> 00:00:01.140\n带 BOM"
        assert convert_vtt(vtt) == "带 BOM"

    def test_unparseable_content_returns_empty_string(self):
        """Input without any valid cue still returns an empty string."""
        vtt = "WEBVTT\n\n这是一段没有时间戳的文本\n"
        assert convert_vtt(vtt) == ""
