"""
Ceal Document Design System — Brother Kit Rules

Non-negotiable constants from Josh's approved TPM prompt.
Every color, font size, margin, and spacing value is exact.
"""
from __future__ import annotations

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter

# ---------------------------------------------------------------------------
# Color Palette
# ---------------------------------------------------------------------------
NAVY = HexColor("#1A2332")
KIT_BLUE = HexColor("#5DADE2")
INK = HexColor("#2C3E50")
SLATE = HexColor("#7F8C8D")

# ---------------------------------------------------------------------------
# Page Setup — US Letter (8.5" x 11")
# ---------------------------------------------------------------------------
PAGE_WIDTH, PAGE_HEIGHT = letter  # 612 x 792 points

# Resume margins
RESUME_MARGIN_TOP = 0.35 * 72      # 25.2pt
RESUME_MARGIN_BOTTOM = 0.3 * 72    # 21.6pt
RESUME_MARGIN_LEFT = 0.5 * 72      # 36pt
RESUME_MARGIN_RIGHT = 0.5 * 72     # 36pt
RESUME_CONTENT_WIDTH = PAGE_WIDTH - RESUME_MARGIN_LEFT - RESUME_MARGIN_RIGHT

# Cover letter margins
CL_MARGIN_TOP = 0.75 * 72          # 54pt
CL_MARGIN_BOTTOM = 0.75 * 72       # 54pt
CL_MARGIN_LEFT = 0.85 * 72         # 61.2pt
CL_MARGIN_RIGHT = 0.85 * 72        # 61.2pt
CL_CONTENT_WIDTH = PAGE_WIDTH - CL_MARGIN_LEFT - CL_MARGIN_RIGHT

# ---------------------------------------------------------------------------
# Font Names (must match font_manager registration)
# ---------------------------------------------------------------------------
ARCHIVO_BOLD = "Archivo-Bold"
ARCHIVO_SEMIBOLD = "Archivo-SemiBold"
INTER_REGULAR = "Inter"
INTER_MEDIUM = "Inter-Medium"
JBMONO_REGULAR = "JBMono"
JBMONO_MEDIUM = "JBMono-Medium"

# ---------------------------------------------------------------------------
# Resume Font Sizes
# ---------------------------------------------------------------------------
RESUME_NAME_SIZE = 20.0
RESUME_TITLE_SIZE = 9.5
RESUME_SECTION_HEADER_SIZE = 9.0
RESUME_JOB_TITLE_SIZE = 8.2
RESUME_BODY_SIZE = 7.8
RESUME_CONTACT_SIZE = 7.8
RESUME_SKILL_LABEL_SIZE = 7.6

# ---------------------------------------------------------------------------
# Cover Letter Font Sizes
# ---------------------------------------------------------------------------
CL_NAME_SIZE = 18.0
CL_CONTACT_SIZE = 8.5
CL_DATE_SIZE = 9.0
CL_SALUTATION_SIZE = 9.5
CL_BODY_SIZE = 9.2
CL_SIGNATURE_SIZE = 10.0
CL_LINK_SIZE = 8.5

# ---------------------------------------------------------------------------
# Spacing Constants
# ---------------------------------------------------------------------------
# Resume
RESUME_SECTION_GAP = 8.0
RESUME_HEADER_RULE_WIDTH = 0.5       # Kit Blue rule thickness (pt)
RESUME_BULLET_INDENT = 12.0
RESUME_BULLET_DOT_RADIUS = 1.8
RESUME_LINE_SPACING = 1.25           # multiplier

# Cover letter
CL_DIVIDER_WIDTH = 1.0              # Kit Blue divider thickness (pt)
CL_LINE_SPACING = 1.45              # multiplier
CL_PARAGRAPH_GAP = 8.0
