"""Unit tests for the rich text parser."""
from __future__ import annotations

from src.document.design_system import INK, INTER_MEDIUM, INTER_REGULAR
from src.document.rich_text import parse_rich_text, rich_segments_to_words


class TestParseRichText:
    def test_parse_no_markup(self):
        """Plain text produces a single normal segment."""
        segs = parse_rich_text("Hello world")
        assert segs == [("Hello world", "normal")]

    def test_parse_bold_markup(self):
        """**bold** text is extracted as a bold segment."""
        segs = parse_rich_text("Saved **$12M** in losses.")
        assert len(segs) == 3
        assert segs[0] == ("Saved ", "normal")
        assert segs[1] == ("$12M", "bold")
        assert segs[2] == (" in losses.", "normal")

    def test_parse_multiple_bold(self):
        """Multiple bold segments in one string."""
        segs = parse_rich_text("**A** and **B** end")
        assert len(segs) == 4
        assert segs[0] == ("A", "bold")
        assert segs[1] == (" and ", "normal")
        assert segs[2] == ("B", "bold")
        assert segs[3] == (" end", "normal")

    def test_parse_unclosed_bold(self):
        """Unclosed ** treated as literal text."""
        segs = parse_rich_text("Open **bold no close")
        assert len(segs) == 1
        assert segs[0][1] == "normal"
        assert "**" in segs[0][0]

    def test_parse_empty_string(self):
        """Empty string returns empty segments list."""
        assert parse_rich_text("") == []


class TestRichSegmentsToWords:
    def test_punctuation_merge(self):
        """Comma after bold word merges onto previous word."""
        segs = [("Saved ", "normal"), ("$12M", "bold"), (", reducing", "normal")]
        words = rich_segments_to_words(segs, INTER_REGULAR, 7.8, INK)
        # "$12M," should be one merged token (bold font for $12M part)
        word_texts = [w[0] for w in words]
        assert "$12M," in word_texts

    def test_punctuation_no_merge_for_words(self):
        """Normal words that happen to follow others aren't merged."""
        segs = [("Hello world", "normal")]
        words = rich_segments_to_words(segs, INTER_REGULAR, 7.8, INK)
        word_texts = [w[0] for w in words]
        assert "Hello" in word_texts
        assert "world" in word_texts

    def test_bold_uses_medium_font(self):
        """Bold words use Inter-Medium font."""
        segs = [("**metric**", "bold")]
        # Need to re-parse since we passed raw segments
        segs = parse_rich_text("Check **metric** here")
        words = rich_segments_to_words(segs, INTER_REGULAR, 7.8, INK)
        bold_words = [w for w in words if w[1] == INTER_MEDIUM]
        assert len(bold_words) > 0

    def test_empty_segments(self):
        """Empty segments list returns empty words."""
        words = rich_segments_to_words([], INTER_REGULAR, 7.8, INK)
        assert words == []
