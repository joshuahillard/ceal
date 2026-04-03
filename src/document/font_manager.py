"""
Ceal Font Manager — registers TTF fonts with ReportLab.

Fonts are committed to data/fonts/ for deterministic Docker builds.
"""
from __future__ import annotations

import os
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

_FONT_MAP = {
    "Archivo-Bold": "Archivo-Bold.ttf",
    "Archivo-SemiBold": "Archivo-SemiBold.ttf",
    "Inter": "Inter-Regular.ttf",
    "Inter-Medium": "Inter-Medium.ttf",
    "JBMono": "JBMono-Regular.ttf",
    "JBMono-Medium": "JBMono-Medium.ttf",
}

_registered = False


def register_fonts(font_dir: str | None = None) -> None:
    """
    Register all project fonts with ReportLab. Idempotent.

    Args:
        font_dir: Path to font directory. Defaults to FONT_DIR env var
                  or data/fonts/ relative to project root.

    Raises:
        FileNotFoundError: If any required font file is missing.
    """
    global _registered
    if _registered:
        return

    if font_dir is None:
        font_dir = os.environ.get("FONT_DIR")
    if font_dir is None:
        # Default: data/fonts/ relative to project root (ceal/)
        font_dir = str(Path(__file__).parent.parent.parent / "data" / "fonts")

    font_path = Path(font_dir)

    missing = []
    for _name, filename in _FONT_MAP.items():
        full_path = font_path / filename
        if not full_path.exists():
            missing.append(str(full_path))

    if missing:
        raise FileNotFoundError(
            f"Missing font files: {', '.join(missing)}. "
            f"Expected in: {font_path}"
        )

    for name, filename in _FONT_MAP.items():
        pdfmetrics.registerFont(TTFont(name, str(font_path / filename)))

    _registered = True


def reset_registration() -> None:
    """Reset registration flag (for testing)."""
    global _registered
    _registered = False
