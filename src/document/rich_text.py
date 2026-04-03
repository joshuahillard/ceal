"""
Ceal Rich Text Parser — **bold** markup rendering for PDF generation.

Supports **bold** for metrics (e.g., **$12M**) with punctuation-aware
word wrapping. Used by the resume generator for bullet rendering.
"""
from __future__ import annotations

import re

from reportlab.lib.colors import Color
from reportlab.pdfbase import pdfmetrics

from src.document.design_system import (
    INK,
    INTER_MEDIUM,
    INTER_REGULAR,
    KIT_BLUE,
    RESUME_BODY_SIZE,
    RESUME_BULLET_DOT_RADIUS,
    RESUME_BULLET_INDENT,
    RESUME_LINE_SPACING,
)

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_PUNCT_CHARS = set(",.;:!?)")


def parse_rich_text(text: str) -> list[tuple[str, str]]:
    """
    Parse **bold** markup into segments.

    Returns:
        List of (text, style) tuples where style is 'bold' or 'normal'.
    """
    if not text:
        return []

    segments: list[tuple[str, str]] = []
    last_end = 0

    for match in _BOLD_RE.finditer(text):
        # Text before this bold match
        if match.start() > last_end:
            segments.append((text[last_end:match.start()], "normal"))
        segments.append((match.group(1), "bold"))
        last_end = match.end()

    # Remaining text after last match
    if last_end < len(text):
        segments.append((text[last_end:], "normal"))

    return segments


def rich_segments_to_words(
    segments: list[tuple[str, str]],
    base_font: str,
    base_size: float,
    color: Color,
) -> list[tuple[str, str, float, Color]]:
    """
    Convert rich text segments to word-level tokens with font info.

    Performs punctuation merging: if a token is pure punctuation, it
    merges onto the preceding word (fixes "JIRA ," spacing bug).

    Returns:
        List of (word, font, size, color) tuples.
    """
    bold_font = INTER_MEDIUM
    raw_words: list[tuple[str, str, float, Color]] = []

    for text_part, style in segments:
        font = bold_font if style == "bold" else base_font
        for word in text_part.split():
            if word:
                raw_words.append((word, font, base_size, color))

    # Punctuation merging pass
    if not raw_words:
        return raw_words

    merged: list[tuple[str, str, float, Color]] = [raw_words[0]]
    for word, font, size, col in raw_words[1:]:
        if word and all(c in _PUNCT_CHARS for c in word) and merged:
            # Merge punctuation onto previous word
            prev_word, prev_font, prev_size, prev_col = merged[-1]
            merged[-1] = (prev_word + word, prev_font, prev_size, prev_col)
        else:
            merged.append((word, font, size, col))

    return merged


def draw_rich_wrapped(
    canvas,
    text: str,
    x: float,
    y: float,
    max_width: float,
    base_font: str = INTER_REGULAR,
    base_size: float = RESUME_BODY_SIZE,
    color: Color = INK,
    line_spacing: float = RESUME_LINE_SPACING,
    justified: bool = False,
) -> float:
    """
    Draw rich text with word wrapping on a ReportLab canvas.

    Returns:
        The y position after the last line.
    """
    segments = parse_rich_text(text)
    words = rich_segments_to_words(segments, base_font, base_size, color)

    if not words:
        return y

    space_width = pdfmetrics.stringWidth(" ", base_font, base_size)
    line_height = base_size * line_spacing

    lines: list[list[tuple[str, str, float, Color]]] = []
    current_line: list[tuple[str, str, float, Color]] = []
    current_width = 0.0

    for word_tuple in words:
        word, font, size, col = word_tuple
        w = pdfmetrics.stringWidth(word, font, size)
        needed = w if not current_line else w + space_width

        if current_line and current_width + needed > max_width:
            lines.append(current_line)
            current_line = [word_tuple]
            current_width = w
        else:
            current_line.append(word_tuple)
            current_width += needed

    if current_line:
        lines.append(current_line)

    for i, line in enumerate(lines):
        is_last_line = (i == len(lines) - 1)
        _draw_word_line(canvas, line, x, y, max_width, space_width, justified and not is_last_line)
        y -= line_height

    return y


def _draw_word_line(
    canvas,
    words: list[tuple[str, str, float, Color]],
    x: float,
    y: float,
    max_width: float,
    base_space: float,
    justified: bool,
) -> None:
    """Draw a single line of mixed-font words."""
    if not words:
        return

    total_text_width = sum(pdfmetrics.stringWidth(w, f, s) for w, f, s, _ in words)
    gap_count = len(words) - 1

    if justified and gap_count > 0:
        space = (max_width - total_text_width) / gap_count
        # Cap space to prevent extreme stretching
        space = min(space, base_space * 4)
    else:
        space = base_space

    cursor_x = x
    for word, font, size, color in words:
        canvas.setFont(font, size)
        canvas.setFillColor(color)
        canvas.drawString(cursor_x, y, word)
        cursor_x += pdfmetrics.stringWidth(word, font, size) + space


def draw_bullet_rich(
    canvas,
    text: str,
    x: float,
    y: float,
    max_width: float,
    base_font: str = INTER_REGULAR,
    base_size: float = RESUME_BODY_SIZE,
    color: Color = INK,
    line_spacing: float = RESUME_LINE_SPACING,
) -> float:
    """
    Draw a Kit Blue bullet dot followed by rich text with wrapping.

    Returns:
        The y position after the last line.
    """
    # Draw bullet dot
    dot_x = x + RESUME_BULLET_DOT_RADIUS
    dot_y = y + base_size * 0.3
    canvas.setFillColor(KIT_BLUE)
    canvas.circle(dot_x, dot_y, RESUME_BULLET_DOT_RADIUS, fill=1, stroke=0)

    # Draw text with indent
    text_x = x + RESUME_BULLET_INDENT
    text_width = max_width - RESUME_BULLET_INDENT

    return draw_rich_wrapped(
        canvas, text, text_x, y, text_width,
        base_font=base_font, base_size=base_size,
        color=color, line_spacing=line_spacing,
    )
