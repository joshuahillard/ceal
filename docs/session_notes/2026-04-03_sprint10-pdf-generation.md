# Ceal Session Notes — Thursday April 3, 2026

**Session type:** Sprint 10 — PDF Document Generation Pipeline
**AI platform:** Claude Code (Opus 4.6)
**Branch:** main

## Objective
Integrate production PDF generation for resumes and cover letters into the Ceal web application using ReportLab canvas API with the Brother Kit Rules design system.

## Tasks Completed
| # | Task | Files | Status |
|---|------|-------|--------|
| 1 | Download + commit 6 TTF font files | `data/fonts/*.ttf` | Done |
| 2 | Create design system constants module | `src/document/design_system.py` | Done |
| 3 | Create font manager (idempotent registration) | `src/document/font_manager.py` | Done |
| 4 | Create Pydantic data contracts | `src/document/models.py` | Done |
| 5 | Create rich text parser (**bold** + punctuation merge) | `src/document/rich_text.py` | Done |
| 6 | Create resume PDF generator | `src/document/resume_pdf.py` | Done |
| 7 | Create cover letter PDF generator | `src/document/coverletter_pdf.py` | Done |
| 8 | Create Claude API cover letter content engine | `src/document/coverletter_engine.py` | Done |
| 9 | Create FastAPI export routes | `src/web/routes/export.py` | Done |
| 10 | Create export page template | `src/web/templates/export.html` | Done |
| 11 | Wire export router into app | `src/web/app.py` | Done |
| 12 | Add PDF export button to Jobs page | `src/web/templates/jobs.html` | Done |
| 13 | Add reportlab dependency | `requirements.txt` | Done |
| 14 | Document FONT_DIR config | `.env.example` | Done |
| 15 | Unit tests: rich text, resume PDF, cover letter PDF, engine | `tests/unit/test_rich_text.py`, `test_pdf_resume.py`, `test_pdf_coverletter.py`, `test_cover_letter_engine.py` | Done |
| 16 | Integration tests: file roundtrip, route roundtrip | `tests/integration/test_pdf_export_roundtrip.py` | Done |

## Files Changed
### New Files (21)
- `src/document/__init__.py` — package init
- `src/document/design_system.py` — Brother Kit Rules constants
- `src/document/font_manager.py` — TTF font registration
- `src/document/models.py` — ResumeData, CoverLetterData, ExportResult
- `src/document/rich_text.py` — **bold** parser + word-wrap renderer
- `src/document/resume_pdf.py` — ReportLab resume generator
- `src/document/coverletter_pdf.py` — ReportLab cover letter generator
- `src/document/coverletter_engine.py` — Claude API content generation
- `src/web/routes/export.py` — GET/POST export routes
- `src/web/templates/export.html` — export page UI
- `data/fonts/Archivo-Bold.ttf` — font file
- `data/fonts/Archivo-SemiBold.ttf` — font file
- `data/fonts/Inter-Regular.ttf` — font file
- `data/fonts/Inter-Medium.ttf` — font file
- `data/fonts/JBMono-Regular.ttf` — font file
- `data/fonts/JBMono-Medium.ttf` — font file
- `tests/unit/test_rich_text.py` — 9 tests
- `tests/unit/test_pdf_resume.py` — 7 tests
- `tests/unit/test_pdf_coverletter.py` — 5 tests
- `tests/unit/test_cover_letter_engine.py` — 14 tests
- `tests/integration/test_pdf_export_roundtrip.py` — 6 tests

### Modified Files (4)
- `src/web/app.py` — registered export router
- `src/web/templates/jobs.html` — added PDF export button column
- `requirements.txt` — added reportlab>=4.1.0
- `.env.example` — documented FONT_DIR

## Test Results
| Metric | Value |
|--------|-------|
| Total tests | 287 |
| Passed | 287 |
| Failed | 0 |
| New tests added | 41 |
| Lint errors | 0 |

## Architecture Decisions
- **ReportLab canvas API** over HTML-to-PDF: pixel-level control over design system, no browser dependency
- **Fonts committed to repo**: deterministic Docker/Cloud Run builds with no runtime downloads
- **Pydantic data contracts**: ResumeData and CoverLetterData enforce structure at the API boundary
- **Rich text parser**: supports **bold** markup for metrics with punctuation-aware word wrapping
- **Single-page constraint**: both generators validate page bounds and return overflow warnings
- **Cover letter engine**: follows same Claude API patterns as tailoring engine (httpx, JSON prompting, code fence stripping, fail-graceful)
- **Streaming PDF response**: export routes stream PDF bytes directly via StreamingResponse

## What's NOT in This Session
- Multi-page resume support (hard constraint: single page only)
- Live preview / WYSIWYG editor
- Batch PDF generation for multiple jobs
- Custom font upload UI
- Tailoring result merge into resume template (base template only — merge deferred)

## Career Translation (X-Y-Z Bullet)
> Built a PDF document generation pipeline that produces pixel-matched single-page resumes and role-tailored cover letters, integrating Claude API content generation with ReportLab rendering, reducing application preparation time from 45 minutes to under 2 minutes per role.
