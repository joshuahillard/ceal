# Ceal Sprint 10 — PDF Document Generation Pipeline (Resume + Cover Letter)

## CONTEXT

You are working on the Ceal project — an AI-powered career signal engine.
The project root is the `ceal/` directory containing `src/`, `tests/`, `pyproject.toml`, `requirements.txt`.

**Read these onboarding docs before starting:**
- `docs/ai-onboarding/PROJECT_CONTEXT.md` — Architecture, file inventory, current state
- `docs/ai-onboarding/PERSONAS.md` — Stakeholder personas and constraints
- `docs/ai-onboarding/RULES.md` — Engineering rules and incident history
- `docs/ai-onboarding/DEBRIEF_TEMPLATE.md` — Session note format

**Branch state**: You are on `main`. Recent commits:
- `1c7dc0e` feat: Sprint 9 — Vertex AI regime classification (optional, fail-open)
- `d054f4e` feat: Sprint 8 — CRM + Auto-Apply reimplementation (reference-locked)
- `98177d4` feat: Docker + polymorphic Cloud SQL support (Sprint 6)

**Current validation baseline**:
- `pytest tests/ -q` -> 246 passed
- `ruff check src/ tests/` -> clean

**This sprint's scope**: Integrate production PDF generation into the Ceal web application. This sprint ports two proven, tested PDF generators (resume + cover letter) into the codebase as a `src/document/` package, adds a Claude-powered cover letter content engine, wires both into FastAPI download routes, and adds export controls to the Jobs page. The PDF output MUST match Josh's exact design system (Brother Kit Rules): Archivo headers, Inter body, Navy/Kit Blue/Ink/Slate color palette, justified text, single-page constraint.

**Reference implementations exist for this sprint.** The authoritative sources are:
1. Current `main` codebase
2. Proven resume PDF generator: `gen_resume_pdf.py` (tested, POC approved by Josh)
3. Proven cover letter PDF generator: `gen_coverletter_pdf.py` (tested, POC approved by Josh)
4. Design system spec: TPM prompt at `Resume_CoverLetter_TPM_Prompt.md`
5. Existing tailoring engine output: `src/tailoring/engine.py` -> `TailoringResult`

**Stakeholders active for this sprint:**
- AI Architect (cover letter content engine)
- ETL Architect (font management, design system, file I/O)
- QA Lead (PDF validation, unit + integration tests)
- DPM (UI integration, career value translation)

---

## CRITICAL RULES (Anti-Hallucination)

### From RULES.md (apply to ALL sprints):
1. **READ before WRITE**: Before modifying ANY file, read it first. Never assume file contents.
2. **No File Duplication**: Do NOT create files that duplicate existing functionality.
3. **Python 3.10+ Target**: No `datetime.UTC`, no `StrEnum`, no `match`, no `X | Y` without `from __future__ import annotations`.
4. **Import Paths**: All imports use `src.` prefix. Project uses `pythonpath = ["."]`.
5. **Async Everywhere**: `AsyncSession`, `async def` for DB and routes, `@pytest.mark.asyncio`.
6. **No Dialect-Specific SQL in Shared Paths**: Use `src.models.compat.is_sqlite()` branching.
7. **No Secrets in Code**: `.env` + `python-dotenv` only.
8. **Ruff**: `py310`, `line-length = 120`. Ignored: `UP017`, `UP042`, `E501`, `SIM102`, `SIM105`, `SIM108`, `B017`, `B904`.
9. **Test Isolation**: `StaticPool` in-memory SQLite, `asyncio_mode = "strict"`.
10. **Dual-Backend Testing**: Raw SQL functions need real SQLite integration tests, not just mocks (Jobs Tab Bug — 3x recurrence).

### Sprint 10-Specific Rules:
11. **Do NOT modify the tailoring engine.** `src/tailoring/engine.py` is protected. The PDF generator consumes its OUTPUT (`TailoringResult`), never reaches into its internals.
12. **Do NOT modify the existing .docx export.** `src/export.py` stays untouched. PDF generation lives in the NEW `src/document/` package.
13. **Font files must be committed to the repo.** Docker/Cloud Run builds must have fonts available without network calls. Bundle TTF files in `data/fonts/`.
14. **Design system constants are NOT negotiable.** The color palette (Navy #1A2332, Kit Blue #5DADE2, Ink #2C3E50, Slate #7F8C8D), font hierarchy (Archivo > Inter > JBMono), and spacing rules come from the TPM prompt. Do NOT improvise alternatives.
15. **Single-page constraint is hard.** Both resume and cover letter MUST fit on one US Letter page. The generator MUST validate this and WARN (not silently overflow).
16. **Cover letter content uses Claude API.** Follow the same patterns as `src/tailoring/engine.py` — httpx client, structured JSON prompting, code fence stripping, fail-graceful. Use the SAME `ANTHROPIC_API_KEY` env var.
17. **Bold markup (**text**) must be preserved in the rendering pipeline.** The rich text parser in the resume generator supports `**bold**` for metrics. Tailored content from Claude must use this markup for key numbers.
18. **Do NOT use python-docx, fpdf, or weasyprint.** ReportLab is the ONLY PDF library. It is already proven in the POC.

### Files That Must NOT Be Modified (Protected — per RULES.md):
| File | Why |
|------|-----|
| `src/tailoring/engine.py` | Semantic fidelity guardrail v1.1 — rejects hallucinated metrics |
| `src/tailoring/models.py` | Pydantic contracts used by engine, persistence, and export |
| `src/tailoring/db_models.py` | SQLAlchemy ORM models for Phase 2 tables |
| `src/tailoring/persistence.py` | Save/retrieve tailoring results |
| `src/models/compat.py` | Backend detection used by database.py, init_db, CI |
| `src/models/entities.py` | Pydantic models used by every pipeline stage (modify ONLY if blocked — explain why) |
| `src/apply/prefill.py` | Deterministic ATS prefill engine |
| `src/export.py` | Existing .docx export — leave untouched |
| `src/ranker/regime_classifier.py` | Sprint 9 Vertex AI classifier |
| `src/ranker/regime_models.py` | Sprint 9 regime Pydantic models |

### Files That Require Explicit Permission (granted for this sprint):
| File | Permitted Change |
|------|-----------------|
| `src/web/app.py` | Register new export router |
| `src/web/templates/jobs.html` | Add "Export Resume PDF" and "Export Cover Letter PDF" action buttons |
| `src/web/templates/base.html` | Add navigation link to export page (if needed) |
| `src/web/static/style.css` | Add minimal styling for export controls |
| `requirements.txt` | Add pinned `reportlab` dependency |
| `.env.example` | Add `FONT_DIR` config var documentation |
| `.github/workflows/ci.yml` | No changes expected this sprint |

---

## PRE-FLIGHT CHECK

Run these commands IN ORDER before starting any work:

```bash
# 1. Verify working directory
pwd
# Must be inside the ceal/ project root

# 2. Verify branch
git branch --show-current
# Must be: main

# 3. Recent commits
git log --oneline -5
# Expect to see Sprint 9 Vertex AI commit (1c7dc0e)

# 4. Uncommitted changes
git status
# If modified files exist, read diffs and decide:
#   - Legitimate additions -> commit with descriptive message
#   - Unexpected -> STOP and report
# If clean, proceed.

# 5. Run all tests
pytest tests/ -q
# Must be: 246 passed. Fix failures before proceeding.

# 6. Verify lint
ruff check src/ tests/
# Must be: clean. Fix errors before proceeding.

# 7. Verify key files this sprint depends on
ls src/tailoring/engine.py
ls src/tailoring/models.py
ls src/tailoring/resume_parser.py
ls src/tailoring/skill_extractor.py
ls src/export.py
ls src/web/app.py
ls src/web/routes/jobs.py
ls src/web/templates/jobs.html
ls src/web/templates/base.html
ls requirements.txt
ls .env.example

# 8. Verify files this sprint will CREATE don't already exist
ls src/document/ 2>&1                                  # Should NOT exist
ls src/web/routes/export.py 2>&1                       # Should NOT exist
ls src/web/templates/export.html 2>&1                  # Should NOT exist
ls tests/unit/test_pdf_resume.py 2>&1                  # Should NOT exist
ls tests/unit/test_pdf_coverletter.py 2>&1             # Should NOT exist
ls tests/unit/test_cover_letter_engine.py 2>&1         # Should NOT exist
ls tests/integration/test_pdf_export_roundtrip.py 2>&1 # Should NOT exist
ls data/fonts/ 2>&1                                    # Should NOT exist

# 9. Verify reference implementations are accessible (outside ceal/ dir)
ls ../../gen_resume_pdf.py 2>&1 || echo "Reference resume generator not found — use specs below"
ls ../../gen_coverletter_pdf.py 2>&1 || echo "Reference cover letter generator not found — use specs below"
```

---

## DESIGN SYSTEM REFERENCE (Brother Kit Rules — NON-NEGOTIABLE)

These are the exact specs from Josh's approved TPM prompt. Every constant below must be reproduced exactly.

### Color Palette
| Name | Hex | Usage |
|------|-----|-------|
| Navy | `#1A2332` | Name, section headers |
| Kit Blue | `#5DADE2` | Title line, bullet dots, links, section rules |
| Ink | `#2C3E50` | Body text, bullet content |
| Slate | `#7F8C8D` | Dates, locations, contact info |

### Typography
| Element | Font | Weight | Size |
|---------|------|--------|------|
| Name | Archivo | Bold | 20pt (resume) / 18pt (cover letter) |
| Title line | Archivo | SemiBold | 9.5pt |
| Section headers | Archivo | SemiBold | 9pt (ALL CAPS) |
| Job titles | Archivo | SemiBold | 8.2pt |
| Body text | Inter | Regular | 7.8pt (resume) / 9.2pt (cover letter) |
| Contact/dates | Inter | Regular | 7.8pt |
| Skill labels | Inter | Medium | 7.6pt |
| Salutation | Inter | Medium | 9.5pt (cover letter) |
| Signature | Archivo | SemiBold | 10pt (cover letter) |

### Resume Layout
- Page: US Letter (8.5" x 11")
- Margins: 0.35" top, 0.3" bottom, 0.5" left/right
- Single page — hard constraint
- Section headers: Kit Blue 0.5px rule above, then ALL CAPS text below
- Bullets: Kit Blue dot, body text in Ink
- Profile paragraph: justified
- Job blocks: "Title, Company" line 1, "Location | Dates" line 2 in Slate
- Project blocks: Name line 1, "Tech stack | Dates" line 2 in Slate
- Skills: bullet + bold label + comma-separated items with wrapping
- Bold markup: `**$12M**` renders in Inter-Medium for key metrics

### Cover Letter Layout
- Page: US Letter (8.5" x 11")
- Margins: 0.75" top/bottom, 0.85" left/right
- Name: left-aligned, Archivo-Bold 18pt, Navy
- Contact: left-aligned, Inter 8.5pt, Slate
- Kit Blue divider: 1.0pt line below contact
- Date, company, role: Inter 9pt, Slate/Ink
- Salutation: Inter-Medium 9.5pt, Navy
- Body: 5 paragraphs, Inter 9.2pt, Ink, justified, line spacing 1.45x
- Closing: "Sincerely," + signature name (Archivo-SemiBold 10pt Navy)
- Links: Inter 8.5pt, Kit Blue

### Required Font Files (Open Source — OFL Licensed)
| File | Source | CDN URL |
|------|--------|---------|
| `Archivo-Bold.ttf` | Google Fonts | `cdn.jsdelivr.net/fontsource/fonts/archivo@latest/latin-700-normal.ttf` |
| `Archivo-SemiBold.ttf` | Google Fonts | `cdn.jsdelivr.net/fontsource/fonts/archivo@latest/latin-600-normal.ttf` |
| `Inter-Regular.ttf` | Google Fonts | `cdn.jsdelivr.net/fontsource/fonts/inter@latest/latin-400-normal.ttf` |
| `Inter-Medium.ttf` | Google Fonts | `cdn.jsdelivr.net/fontsource/fonts/inter@latest/latin-500-normal.ttf` |
| `JBMono-Regular.ttf` | JetBrains | `cdn.jsdelivr.net/fontsource/fonts/jetbrains-mono@latest/latin-400-normal.ttf` |
| `JBMono-Medium.ttf` | JetBrains | `cdn.jsdelivr.net/fontsource/fonts/jetbrains-mono@latest/latin-500-normal.ttf` |

### Cover Letter 5-Paragraph Arc (Claude Content Generation)
| # | Section | Content |
|---|---------|---------|
| 1 | Hook | Company mission resonance + personal connection + why this role |
| 2 | Toast Credibility | $12M save, 37% reduction, executive visibility, cross-functional governance |
| 3 | Bridge (Builder) | Ceal + Moss Lane projects, technical fluency, sprint management |
| 4 | Dual Perspective | Leadership + technical depth, rare combination for the role |
| 5 | Close | Location/availability + CTA for conversation |

---

## OUT OF SCOPE

- Modifying the tailoring engine or Claude ranker
- Modifying the existing .docx export module
- Browser automation or ATS form submission
- Multi-page resume support (single-page is a hard requirement)
- Custom font upload UI
- Print-to-PDF from HTML (we use ReportLab canvas, not HTML-to-PDF)
- Live preview / WYSIWYG editor in the browser
- Batch PDF generation for multiple jobs at once
- Changes to any protected file listed above

---

## FILE INVENTORY

### Files to Create (new)
| # | File | Lines (approx) | Purpose |
|---|------|----------------|---------|
| 1 | `src/document/__init__.py` | ~5 | Package init with public API exports |
| 2 | `src/document/design_system.py` | ~80 | Shared constants: colors, fonts, sizes, spacing, page setup |
| 3 | `src/document/rich_text.py` | ~100 | Rich text parser (**bold** markup) + mixed-font word-wrap renderer |
| 4 | `src/document/resume_pdf.py` | ~200 | Resume PDF generator using ReportLab canvas |
| 5 | `src/document/coverletter_pdf.py` | ~150 | Cover letter PDF generator using ReportLab canvas |
| 6 | `src/document/coverletter_engine.py` | ~120 | Claude API cover letter content generation (5-paragraph arc) |
| 7 | `src/document/font_manager.py` | ~60 | Font registration + path resolution from `data/fonts/` |
| 8 | `src/document/models.py` | ~80 | Pydantic models: ResumeData, CoverLetterData, ExportResult |
| 9 | `src/web/routes/export.py` | ~120 | FastAPI routes: POST /export/resume, POST /export/cover-letter |
| 10 | `src/web/templates/export.html` | ~80 | Export page: job details + generate buttons + download links |
| 11 | `data/fonts/Archivo-Bold.ttf` | binary | Font file |
| 12 | `data/fonts/Archivo-SemiBold.ttf` | binary | Font file |
| 13 | `data/fonts/Inter-Regular.ttf` | binary | Font file |
| 14 | `data/fonts/Inter-Medium.ttf` | binary | Font file |
| 15 | `data/fonts/JBMono-Regular.ttf` | binary | Font file |
| 16 | `data/fonts/JBMono-Medium.ttf` | binary | Font file |
| 17 | `tests/unit/test_pdf_resume.py` | ~150 | Resume generator tests (structure, overflow, markup) |
| 18 | `tests/unit/test_pdf_coverletter.py` | ~100 | Cover letter generator tests (layout, justified, bounds) |
| 19 | `tests/unit/test_cover_letter_engine.py` | ~120 | Cover letter Claude integration (mocked API, parsing, arc validation) |
| 20 | `tests/unit/test_rich_text.py` | ~80 | Rich text parser + punctuation merge + word-wrap edge cases |
| 21 | `tests/integration/test_pdf_export_roundtrip.py` | ~100 | End-to-end: tailoring result -> PDF bytes -> file validation |

### Files to Modify (existing)
| # | File | Changes |
|---|------|---------|
| 22 | `src/web/app.py` | Register `export.router` with `include_router()` |
| 23 | `src/web/templates/jobs.html` | Add "Export PDF" action button per job row |
| 24 | `requirements.txt` | Add pinned `reportlab` dependency |
| 25 | `.env.example` | Add `FONT_DIR` documentation (default: `data/fonts`) |

---

## TASK 0: Read All Files That Will Be Modified

Before writing ANY code, read these files IN FULL:

```
src/web/app.py
src/web/templates/jobs.html
src/web/templates/base.html
src/web/static/style.css
requirements.txt
.env.example
```

Also read for reference (do NOT modify):
```
docs/ai-onboarding/PROJECT_CONTEXT.md
docs/ai-onboarding/PERSONAS.md
docs/ai-onboarding/RULES.md
src/tailoring/engine.py
src/tailoring/models.py
src/tailoring/resume_parser.py
src/tailoring/skill_extractor.py
src/export.py
src/models/database.py
src/models/entities.py
src/web/routes/jobs.py
src/web/routes/dashboard.py
```

---

## TASK 1: Download and Commit Font Files

**Persona**: [ETL Architect] — Font files must be binary-valid TTF. Verify each file with `file` command.

Create `data/fonts/` directory and download all 6 TTF font files from the CDN URLs listed in the Design System Reference above.

**Download method** (use curl or Python — verify each file):
```bash
mkdir -p data/fonts

# Download each font (static weight-specific files, NOT variable fonts)
curl -L -o data/fonts/Archivo-Bold.ttf "https://cdn.jsdelivr.net/fontsource/fonts/archivo@latest/latin-700-normal.ttf"
curl -L -o data/fonts/Archivo-SemiBold.ttf "https://cdn.jsdelivr.net/fontsource/fonts/archivo@latest/latin-600-normal.ttf"
curl -L -o data/fonts/Inter-Regular.ttf "https://cdn.jsdelivr.net/fontsource/fonts/inter@latest/latin-400-normal.ttf"
curl -L -o data/fonts/Inter-Medium.ttf "https://cdn.jsdelivr.net/fontsource/fonts/inter@latest/latin-500-normal.ttf"
curl -L -o data/fonts/JBMono-Regular.ttf "https://cdn.jsdelivr.net/fontsource/fonts/jetbrains-mono@latest/latin-400-normal.ttf"
curl -L -o data/fonts/JBMono-Medium.ttf "https://cdn.jsdelivr.net/fontsource/fonts/jetbrains-mono@latest/latin-500-normal.ttf"
```

**Verification** (CRITICAL — previous sprint hit GitHub LFS 302 redirects serving HTML instead of TTF):
```bash
file data/fonts/Archivo-Bold.ttf      # Must say "TrueType Font data"
file data/fonts/Archivo-SemiBold.ttf   # Must say "TrueType Font data"
file data/fonts/Inter-Regular.ttf      # Must say "TrueType Font data"
file data/fonts/Inter-Medium.ttf       # Must say "TrueType Font data"
file data/fonts/JBMono-Regular.ttf     # Must say "TrueType Font data"
file data/fonts/JBMono-Medium.ttf      # Must say "TrueType Font data"
```

If ANY file is NOT TrueType Font data (e.g., "HTML document"), the download was redirected. STOP, try alternative URLs, or fetch from Google Fonts CDN directly.

---

## TASK 2: Create Document Package Foundation

**Read first**: `src/tailoring/models.py`, `src/models/entities.py`, `src/export.py`

**Persona**: [ETL Architect] — This task establishes the shared design system and data models. Every constant must match the Design System Reference above exactly.

### 2a: Create `src/document/__init__.py`
```python
"""Ceal Document Generation — PDF resume and cover letter export."""
from src.document.resume_pdf import generate_resume_pdf
from src.document.coverletter_pdf import generate_cover_letter_pdf

__all__ = ["generate_resume_pdf", "generate_cover_letter_pdf"]
```

### 2b: Create `src/document/design_system.py`
Extract ALL design constants from the Design System Reference into a single module:
- Color constants (NAVY, KIT_BLUE, INK, SLATE) as ReportLab HexColor objects
- Page setup (margins, content width) for both resume and cover letter
- Font size constants for every text element
- Spacing constants (section gaps, line multipliers, bullet indents)
- Font name constants mapped to filenames

### 2c: Create `src/document/font_manager.py`
- Function `register_fonts(font_dir: str | None = None)` that:
  - Defaults to `data/fonts/` relative to project root if `font_dir` is None
  - Falls back to `FONT_DIR` env var if set
  - Registers all 6 fonts with ReportLab `pdfmetrics.registerFont()`
  - Raises `FileNotFoundError` with clear message if any font file is missing
  - Is idempotent (safe to call multiple times)

### 2d: Create `src/document/models.py`
Pydantic models for the PDF generation data contracts:

```python
# Scaffold — adapt to match existing codebase style
from __future__ import annotations
from pydantic import BaseModel, Field

class ResumeJobEntry(BaseModel):
    title: str
    company: str
    location: str
    dates: str
    bullets: list[str]

class ResumeProjectEntry(BaseModel):
    name: str
    tech: str
    dates: str
    bullets: list[str]

class ResumeSkillCategory(BaseModel):
    label: str
    items: str

class ResumeData(BaseModel):
    """Complete data contract for resume PDF generation."""
    name: str
    title_line: str
    contact: str
    links: str
    profile: str
    experience: list[ResumeJobEntry] = Field(default_factory=list)
    projects: list[ResumeProjectEntry] = Field(default_factory=list)
    skills: list[ResumeSkillCategory] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    section_order: list[str] = Field(default=["experience", "projects"])

class CoverLetterData(BaseModel):
    """Complete data contract for cover letter PDF generation."""
    name: str
    contact: str
    date: str
    company: str
    role: str
    salutation: str = "Dear Hiring Team,"
    paragraphs: list[str] = Field(..., min_length=3, max_length=6)
    closing: str = "Sincerely,"
    signature_name: str
    links: str

class ExportResult(BaseModel):
    """Result of a PDF generation operation."""
    success: bool
    file_path: str | None = None
    file_bytes: bytes | None = None
    final_y: float = 0.0
    overflow: bool = False
    error: str | None = None
```

**Verification**:
```bash
python -c "from src.document.models import ResumeData, CoverLetterData, ExportResult; print('Models OK')"
python -c "from src.document.font_manager import register_fonts; print('Font manager OK')"
python -c "from src.document.design_system import NAVY, KIT_BLUE, INK, SLATE; print('Design system OK')"
ruff check src/document/
```

---

## TASK 3: Create Rich Text Parser

**Read first**: The `parse_rich_text()` and `rich_segments_to_words()` functions in the proven `gen_resume_pdf.py` reference

**Persona**: [QA Lead] — This module is the text rendering core. It must handle edge cases: empty strings, unclosed markup, punctuation after markup boundaries, multi-line wrapping with mixed fonts.

Create `src/document/rich_text.py` with:

1. **`parse_rich_text(text: str) -> list[tuple[str, str]]`**
   - Parses `**bold**` markup into `(text, "bold")` segments
   - All other text produces `(text, "normal")` segments
   - Handles edge cases: unclosed `**`, empty text, no markup

2. **`rich_segments_to_words(segments, base_font, base_size, color) -> list[tuple]`**
   - Converts segments to word-level tokens: `(word, font, size, color)`
   - **Punctuation merging**: If a token is pure punctuation (`,`, `.`, `;`, `:`, `!`, `?`, `)`) and follows a word, merge it onto the preceding word (fixes "JIRA ," spacing bug)
   - Bold words use `Inter-Medium` at `base_size`
   - Normal words use `base_font` at `base_size`

3. **`draw_rich_wrapped(canvas, text, x, y, max_width, ...) -> float`**
   - Word-wraps rich text across lines
   - Supports justified and left-aligned modes
   - Returns y position after last line
   - Uses ReportLab `pdfmetrics.stringWidth()` for accurate measurement

4. **`draw_bullet_rich(canvas, text, x, y, max_width, ...) -> float`**
   - Kit Blue bullet dot + rich text body with wrapping
   - Returns y after

**Note**: The POC reference had `mono` backtick support. Josh approved removing monospace — this sprint uses ONLY `**bold**` markup for metrics. Do NOT implement backtick/mono parsing.

**Verification**:
```bash
python -c "
from src.document.rich_text import parse_rich_text, rich_segments_to_words
# Test basic parsing
segs = parse_rich_text('Saved **\$12M** in losses.')
assert len(segs) == 3
assert segs[1] == ('\$12M', 'bold')
# Test punctuation merging
from src.document.design_system import INK
words = rich_segments_to_words(segs, 'Inter', 7.8, INK)
# 'losses.' should be one token, not 'losses' + '.'
print('Rich text parser OK')
"
ruff check src/document/rich_text.py
```

---

## TASK 4: Create Resume PDF Generator

**Read first**: `gen_resume_pdf.py` (proven reference), `src/document/design_system.py`, `src/document/models.py`

**Persona**: [ETL Architect] — Port the proven generator into the Ceal package. Use constants from `design_system.py`, data contract from `models.py`, rendering from `rich_text.py`.

Create `src/document/resume_pdf.py` with:

**Function**: `generate_resume_pdf(data: ResumeData, output_path: str | None = None) -> ExportResult`

**Behavior**:
- If `output_path` is provided, write PDF to file
- Always return `ExportResult` with `file_bytes` (in-memory PDF for HTTP streaming)
- Use `io.BytesIO` for in-memory generation
- Call `register_fonts()` at module level (idempotent)
- Validate single-page constraint: set `overflow=True` in result if `final_y < MARGIN_BOTTOM`

**Layout sequence** (from proven reference):
1. Header: centered name (Archivo-Bold 20pt Navy)
2. Title line: centered (Archivo-SemiBold 9.5pt Kit Blue)
3. Contact: centered (Inter 7.8pt Slate)
4. Links: centered (Inter 7.8pt Kit Blue)
5. Section gap
6. Professional Profile: section header + justified rich text
7. Ordered sections (experience/projects):
   - Section header with Kit Blue rule
   - Job blocks: "Title, Company" line + "Location | Dates" line
   - Project blocks: Name line + "Tech | Dates" line
   - Bullets with Kit Blue dots and rich text
8. Skills: bullet + Inter-Medium label + items with wrapping
9. Certifications: bullets
10. Education: bullets

**Section header rendering** (from proven reference — TESTED AND APPROVED):
- Kit Blue rule drawn at current y
- Header text baseline at `y - SECTION_HEADER_SIZE * 1.1`
- Content starts at `text_y - SECTION_HEADER_SIZE * 0.9`
- This specific math was debugged through 4 iterations — do NOT change the offsets

**Verification**:
```bash
python -c "
from src.document.models import ResumeData
from src.document.resume_pdf import generate_resume_pdf
# Minimal test data
data = ResumeData(
    name='TEST USER', title_line='Test Title', contact='Test Contact',
    links='test.com', profile='Test profile text.',
    experience=[], projects=[], skills=[], certifications=[], education=[]
)
result = generate_resume_pdf(data)
assert result.success
assert result.file_bytes is not None
assert len(result.file_bytes) > 0
assert not result.overflow
print(f'Resume PDF OK — {len(result.file_bytes)} bytes, final_y={result.final_y:.1f}')
"
ruff check src/document/resume_pdf.py
```

---

## TASK 5: Create Cover Letter PDF Generator

**Read first**: `gen_coverletter_pdf.py` (proven reference), `src/document/design_system.py`, `src/document/models.py`

**Persona**: [ETL Architect] — Port the proven cover letter generator. Simpler than resume (no rich text, justified paragraphs only).

Create `src/document/coverletter_pdf.py` with:

**Function**: `generate_cover_letter_pdf(data: CoverLetterData, output_path: str | None = None) -> ExportResult`

**Behavior**: Same pattern as resume generator (file + bytes, overflow check)

**Layout sequence** (from proven reference):
1. Name: left-aligned, Archivo-Bold 18pt Navy
2. Contact: left-aligned, Inter 8.5pt Slate
3. Kit Blue divider: 1.0pt line
4. Date: Inter 9pt Slate
5. Company + Role: Inter 9pt Ink
6. Salutation: Inter-Medium 9.5pt Navy
7. Body paragraphs: Inter 9.2pt Ink, justified, 1.45x line spacing, 8pt paragraph gap
8. Closing: Inter 9.2pt Ink
9. Signature: Archivo-SemiBold 10pt Navy
10. Links: Inter 8.5pt Kit Blue

**Verification**:
```bash
python -c "
from src.document.models import CoverLetterData
from src.document.coverletter_pdf import generate_cover_letter_pdf
data = CoverLetterData(
    name='Test User', contact='Boston, MA | test@test.com', date='April 3, 2026',
    company='Test Corp', role='Test Role', salutation='Dear Hiring Team,',
    paragraphs=['Test paragraph one.', 'Test paragraph two.', 'Test paragraph three.'],
    closing='Sincerely,', signature_name='Test User', links='linkedin.com/test'
)
result = generate_cover_letter_pdf(data)
assert result.success
assert not result.overflow
print(f'Cover letter PDF OK — {len(result.file_bytes)} bytes, final_y={result.final_y:.1f}')
"
ruff check src/document/coverletter_pdf.py
```

---

## TASK 6: Create Cover Letter Content Engine

**Read first**: `src/tailoring/engine.py` (for Claude API pattern), `src/tailoring/models.py` (for Pydantic output pattern)

**Persona**: [AI Architect] — This module calls Claude to generate cover letter paragraphs. Follow the SAME patterns as `engine.py`: httpx client, structured JSON prompting, code fence stripping, validation, fail-graceful.

Create `src/document/coverletter_engine.py` with:

**Function**: `async def generate_cover_letter_content(job_title: str, company_name: str, job_description: str, resume_profile: str, special_instructions: str = "") -> CoverLetterData | None`

**Behavior**:
- Calls Claude API with a structured prompt requesting 5-paragraph cover letter
- Prompt includes: Josh's profile summary, the 5-paragraph arc structure, job details
- Requests JSON response: `{"paragraphs": ["...", "...", "...", "...", "..."]}`
- Strips markdown code fences (```json ... ```) before parsing
- Validates: exactly 3-6 paragraphs, each non-empty
- Returns `None` on any failure (fail-graceful, log warning)
- Uses `ANTHROPIC_API_KEY` from env (same as tailoring engine)
- Uses `ANTHROPIC_MODEL` from env (default: `claude-sonnet-4-20250514`)
- Tracks prompt version: `COVER_LETTER_PROMPT_VERSION = "v1.0"`

**Claude Prompt Structure** (embedded in the module):
- System: "You are a professional cover letter writer. Generate exactly 5 paragraphs..."
- Include the 5-paragraph arc from Design System Reference
- Include Josh's profile highlights (Toast, $12M, projects)
- Include the job description
- Request JSON output format
- Include special_instructions if provided (for role-specific customization)

**Verification**:
```bash
python -c "from src.document.coverletter_engine import generate_cover_letter_content; print('Cover letter engine OK')"
ruff check src/document/coverletter_engine.py
```

---

## TASK 7: Create FastAPI Export Routes

**Read first**: `src/web/routes/jobs.py`, `src/web/routes/dashboard.py`, `src/web/app.py`

**Persona**: [DPM] — These routes connect the PDF generators to the web UI. Users should be able to generate and download PDFs from the Jobs page.

Create `src/web/routes/export.py` with:

1. **`GET /export/{job_id}`** — Export page showing job details + generate buttons
   - Fetch job listing from database
   - Render `export.html` template with job data
   - Show "Generate Resume PDF" and "Generate Cover Letter PDF" buttons

2. **`POST /export/{job_id}/resume`** — Generate tailored resume PDF
   - Fetch job listing from database
   - Check if tailoring result exists for this job (from `tailoring_requests` table)
   - If yes: merge tailored bullets with base resume template -> generate PDF
   - If no: use base (untailored) resume template -> generate PDF
   - Return PDF as downloadable `StreamingResponse` with filename `{company}_{role}_Resume.pdf`

3. **`POST /export/{job_id}/cover-letter`** — Generate cover letter PDF
   - Fetch job listing from database
   - Call `generate_cover_letter_content()` with job details
   - If content generation succeeds: generate PDF, return as `StreamingResponse`
   - If fails: return error page with helpful message
   - Filename: `{company}_{role}_CoverLetter.pdf`

**Base resume template**: Create a helper function `get_base_resume_data() -> ResumeData` that returns Josh's standard resume data (same content as the POC). This serves as the starting template that the tailoring engine can modify per role.

Create `src/web/templates/export.html`:
- Extends `base.html`
- Shows: Job title, company, match score, tier
- Two action buttons: "Download Resume PDF" and "Download Cover Letter PDF"
- Status messages for generation progress/errors
- Link back to Jobs page

**Verification**:
```bash
python -c "from src.web.routes.export import router; print(f'Export router OK — {len(router.routes)} routes')"
ruff check src/web/routes/export.py
```

---

## TASK 8: Wire Export Router into App

**Read first**: `src/web/app.py`, `src/web/templates/jobs.html`

**Persona**: [DPM] — Minimal changes to existing files. Add export router registration and Jobs page button.

1. **`src/web/app.py`**: Add `from src.web.routes import export` and `app.include_router(export.router)`

2. **`src/web/templates/jobs.html`**: For each job row, add an "Export" link/button that navigates to `/export/{job_id}`

3. **`requirements.txt`**: Add `reportlab>=4.1.0`

4. **`.env.example`**: Add:
```bash
# PDF Generation (optional — defaults shown)
FONT_DIR=data/fonts
```

**Verification**:
```bash
python -c "
from src.web.app import create_app
app = create_app()
routes = [r.path for r in app.routes]
assert '/export/{job_id}' in routes or any('/export' in r for r in routes)
print(f'App routes OK — export routes registered')
"
grep "reportlab" requirements.txt
grep "FONT_DIR" .env.example
```

---

## TASK 9: Add Unit Tests

**Read first**: `tests/unit/test_ranker.py`, `tests/unit/test_web.py` (for style)

**Persona**: [QA Lead] — Comprehensive tests for all new modules. No live API calls. Mock Claude for cover letter engine.

### 9a: Create `tests/unit/test_rich_text.py`
| Test | What it covers |
|------|---------------|
| `test_parse_no_markup` | Plain text -> single normal segment |
| `test_parse_bold_markup` | `**$12M**` -> bold segment extracted |
| `test_parse_multiple_bold` | Multiple bold segments in one string |
| `test_parse_unclosed_bold` | Unclosed `**` treated as literal text |
| `test_parse_empty_string` | Empty string -> empty segments list |
| `test_punctuation_merge` | Comma after bold word merges: "**X**," -> one token |
| `test_punctuation_no_merge_for_words` | Normal words with commas stay separate |

### 9b: Create `tests/unit/test_pdf_resume.py`
| Test | What it covers |
|------|---------------|
| `test_minimal_resume_generates` | Minimal ResumeData -> valid PDF bytes |
| `test_full_resume_generates` | Complete ResumeData (all sections) -> valid PDF bytes |
| `test_resume_single_page` | Full Josh resume data -> `overflow == False` |
| `test_resume_overflow_detected` | Extremely long content -> `overflow == True` |
| `test_resume_pdf_starts_with_magic` | Output bytes start with `%PDF-` |
| `test_resume_file_output` | `output_path` provided -> file exists on disk |
| `test_resume_section_order` | `section_order=["projects", "experience"]` -> projects first |

### 9c: Create `tests/unit/test_pdf_coverletter.py`
| Test | What it covers |
|------|---------------|
| `test_minimal_cover_letter_generates` | Minimal CoverLetterData -> valid PDF bytes |
| `test_cover_letter_single_page` | 5-paragraph WHOOP letter -> `overflow == False` |
| `test_cover_letter_overflow_detected` | 10 very long paragraphs -> `overflow == True` |
| `test_cover_letter_pdf_starts_with_magic` | Output bytes start with `%PDF-` |
| `test_cover_letter_paragraph_count_validation` | Pydantic rejects < 3 or > 6 paragraphs |

### 9d: Create `tests/unit/test_cover_letter_engine.py`
| Test | What it covers |
|------|---------------|
| `test_valid_response_parsing` | Valid JSON with 5 paragraphs -> CoverLetterData |
| `test_code_fence_stripping` | Response wrapped in ```json ... ``` still parses |
| `test_fail_graceful_missing_api_key` | No ANTHROPIC_API_KEY -> returns None |
| `test_fail_graceful_api_error` | Mocked API raises -> returns None |
| `test_fail_graceful_bad_json` | Garbage response -> returns None |
| `test_paragraph_count_validation` | Response with 2 paragraphs -> rejected |
| `test_prompt_version_tracked` | `COVER_LETTER_PROMPT_VERSION` exists and is a string |

**Verification**:
```bash
pytest tests/unit/test_rich_text.py tests/unit/test_pdf_resume.py tests/unit/test_pdf_coverletter.py tests/unit/test_cover_letter_engine.py -v
```

---

## TASK 10: Add Integration Tests

**Read first**: `tests/integration/test_persistence_roundtrip.py`, `tests/integration/test_crm_autoapply_roundtrip.py`

**Persona**: [QA Lead] + [ETL Architect] — End-to-end tests with real file I/O and SQLite.

Create `tests/integration/test_pdf_export_roundtrip.py`:

| Test | What it covers |
|------|---------------|
| `test_resume_pdf_file_roundtrip` | Generate PDF -> write to temp file -> read back -> valid PDF header |
| `test_coverletter_pdf_file_roundtrip` | Generate PDF -> write to temp file -> read back -> valid PDF header |
| `test_resume_from_tailoring_result` | Create TailoringResult -> merge with base template -> generate PDF |
| `test_export_route_resume_returns_pdf` | FastAPI test client -> POST /export/1/resume -> 200 + PDF content-type |
| `test_export_route_cover_letter_returns_pdf` | FastAPI test client -> POST /export/1/cover-letter -> 200 + PDF content-type |

**Verification**:
```bash
pytest tests/integration/test_pdf_export_roundtrip.py -v
```

---

## TASK 11: Full Verification

**Persona**: [QA Lead] — Full suite, zero regressions.

```bash
# Run full test suite
pytest tests/ -v

# Verify lint
ruff check src/ tests/

# Count tests (should be > 246)
pytest tests/ --co -q 2>&1 | tail -3

# Verify PDF generation works standalone (no web server needed)
python -c "
from src.document.models import ResumeData
from src.document.resume_pdf import generate_resume_pdf
data = ResumeData(
    name='JOSHUA HILLARD',
    title_line='Technical Leader | Program Management & Cloud Engineering',
    contact='Boston, MA | (781) 308-0407 | joshua.hillard4@gmail.com',
    links='linkedin.com/in/joshua-hillard | github.com/joshuahillard',
    profile='Technical leader with 10+ years in tech.',
    experience=[], projects=[], skills=[], certifications=[], education=[]
)
result = generate_resume_pdf(data)
print(f'Resume: {len(result.file_bytes)} bytes, overflow={result.overflow}')
assert result.success
print('Standalone PDF generation OK')
"

# Verify existing .docx export still works (not broken)
python -c "from src.export import export_tailoring_result; print('Existing .docx export still importable')"

# Verify font files are committed
ls -la data/fonts/*.ttf | wc -l
# Should be: 6
```

**Acceptance criteria**:
- [ ] Full suite green (246+ existing tests pass, new tests pass)
- [ ] Lint clean
- [ ] 6 TTF font files committed in `data/fonts/`
- [ ] Resume PDF generates from `ResumeData` model with correct layout
- [ ] Cover letter PDF generates from `CoverLetterData` model with correct layout
- [ ] Both PDFs fit on single page with no overflow for standard content
- [ ] Cover letter engine generates content via Claude API (mocked in tests)
- [ ] Export routes return downloadable PDFs from FastAPI
- [ ] Jobs page has export buttons
- [ ] Existing .docx export still works
- [ ] No protected files modified
- [ ] Design system constants match TPM prompt exactly (colors, fonts, sizes)

---

## TASK 12: Create Session Note

**Persona**: [DPM]

Create: `docs/session_notes/YYYY-MM-DD_sprint10-pdf-generation.md`

Use the format from `docs/ai-onboarding/DEBRIEF_TEMPLATE.md`. Document:
- What document generation capabilities were added
- Design system spec compliance (Brother Kit Rules)
- Font management approach (committed TTF files)
- Cover letter content engine architecture
- Integration with existing tailoring pipeline
- Exact tests added
- Career Translation (X-Y-Z bullet):
  - "Built a PDF document generation pipeline that produces pixel-matched single-page resumes and role-tailored cover letters, integrating Claude API content generation with ReportLab rendering, reducing application preparation time from 45 minutes to under 2 minutes per role."

---

## COMMIT

```bash
git add src/document/ \
        src/web/routes/export.py \
        src/web/templates/export.html \
        src/web/app.py \
        src/web/templates/jobs.html \
        data/fonts/ \
        requirements.txt \
        .env.example \
        tests/unit/test_rich_text.py \
        tests/unit/test_pdf_resume.py \
        tests/unit/test_pdf_coverletter.py \
        tests/unit/test_cover_letter_engine.py \
        tests/integration/test_pdf_export_roundtrip.py \
        docs/session_notes/

git status

git commit -m "feat: Sprint 10 — PDF document generation pipeline (resume + cover letter)

Add production PDF generation for resumes and cover letters using Brother Kit Rules design system.
- ReportLab-based resume generator with rich text (**bold** metrics) and justified profile
- ReportLab-based cover letter generator matching approved WHOOP reference layout
- Claude API cover letter content engine (5-paragraph arc, fail-graceful)
- Pydantic data contracts: ResumeData, CoverLetterData, ExportResult
- FastAPI export routes with downloadable PDF streaming
- Jobs page export buttons
- 6 committed TTF font files (Archivo, Inter, JetBrains Mono)
- Unit tests (parsing, generation, validation) + integration tests (file I/O, routes)
- Existing .docx export and tailoring engine UNCHANGED

Co-authored-by: Josh Hillard <joshua.hillard4@gmail.com>"

git tag -a v2.10.0-sprint10-pdf-generation -m "Sprint 10: PDF document generation pipeline"
git push origin main --tags
```

---

## COMPLETION CHECKLIST

- [ ] `data/fonts/` — 6 TTF font files committed (verified as TrueType)
- [ ] `src/document/__init__.py` — package init with public API
- [ ] `src/document/design_system.py` — all design constants matching TPM prompt
- [ ] `src/document/rich_text.py` — rich text parser with **bold** support + punctuation merge
- [ ] `src/document/font_manager.py` — idempotent font registration
- [ ] `src/document/models.py` — ResumeData, CoverLetterData, ExportResult
- [ ] `src/document/resume_pdf.py` — resume generator with overflow detection
- [ ] `src/document/coverletter_pdf.py` — cover letter generator with overflow detection
- [ ] `src/document/coverletter_engine.py` — Claude API content generation (fail-graceful)
- [ ] `src/web/routes/export.py` — GET + POST routes for PDF download
- [ ] `src/web/templates/export.html` — export page UI
- [ ] `src/web/app.py` — export router registered
- [ ] `src/web/templates/jobs.html` — export buttons added
- [ ] `requirements.txt` — `reportlab` pinned
- [ ] `.env.example` — `FONT_DIR` documented
- [ ] `tests/unit/test_rich_text.py` — 7+ parser tests
- [ ] `tests/unit/test_pdf_resume.py` — 7+ resume generator tests
- [ ] `tests/unit/test_pdf_coverletter.py` — 5+ cover letter generator tests
- [ ] `tests/unit/test_cover_letter_engine.py` — 7+ Claude integration tests (mocked)
- [ ] `tests/integration/test_pdf_export_roundtrip.py` — 5+ end-to-end tests
- [ ] `docs/session_notes/` — session note created
- [ ] `pytest tests/ -v` — ALL pass (246+ existing + new)
- [ ] `ruff check src/ tests/` — 0 errors
- [ ] Existing `.docx` export still works
- [ ] Existing tailoring engine UNCHANGED
- [ ] No protected files modified
- [ ] Committed and tagged `v2.10.0-sprint10-pdf-generation`
- [ ] Pushed to `origin/main`

---

## DESIGN GUARDRAILS (Interview Defense)

This sprint should be easy to defend in an interview:
- "The PDF generators use ReportLab canvas API for pixel-level control over the design system"
- "Fonts are committed to the repo for deterministic Docker builds — no runtime downloads"
- "Cover letter content is generated by Claude with a structured 5-paragraph arc prompt"
- "The Pydantic data contracts (ResumeData, CoverLetterData) enforce structure at the API boundary"
- "Rich text parsing supports **bold** markup for metrics, with punctuation-aware word wrapping"
- "Both documents validate the single-page constraint and return overflow warnings"
- "The export routes stream PDF bytes directly — no temp files in the HTTP path"
- "All Claude integration is fail-graceful: if the API is down, the route returns a clear error, not a 500"

If the implementation starts drifting into "HTML-to-PDF conversion" or "multi-page resume support" or "live preview editor," STOP and reset to the scope above.
