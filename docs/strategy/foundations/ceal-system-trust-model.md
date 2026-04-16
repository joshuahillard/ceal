# Ceal System Trust Model

*What the system may accept, must verify, and where final authority lives.*

---

## Core Concept

A trust model defines which system outputs can be acted on directly, which must be validated before downstream use, and which require human review before influencing career-critical decisions. Ceal processes job listings through an LLM-assisted pipeline that ultimately produces resumes, cover letters, and application submissions — artifacts that directly impact Josh's career trajectory. Trust failures here are not abstract: a hallucinated metric on a resume or a misranked listing wastes real application slots.

---

## Deterministic vs. Non-Deterministic Components

**Deterministic components** form the control structure. Their behavior is reproducible and testable:
- Scrapers (`src/scrapers/linkedin.py`) — HTML parsing with known input/output
- Normalizer (`src/normalizer/pipeline.py`) — salary extraction, skill matching, HTML cleanup
- Pydantic models (`src/models/entities.py`) — structural validation at every boundary
- Database operations (`src/models/database.py`) — idempotent upserts via ON CONFLICT
- ATS prefill engine (`src/apply/prefill.py`) — deterministic field mapping, no randomness
- PDF rendering (`src/document/resume_pdf.py`, `coverletter_pdf.py`) — ReportLab pixel-level control

**Non-deterministic components** must be constrained by deterministic layers:
- Claude API scoring (`src/ranker/llm_ranker.py`) — produces 0.0–1.0 fit scores
- Claude API tailoring (`src/tailoring/engine.py`) — rewrites resume bullets in X-Y-Z format
- Claude API cover letter generation (`src/document/coverletter_engine.py`) — generates letter content
- Vertex AI regime classification (`src/ranker/regime_classifier.py`) — optional tier classification

---

## Three Categories of Information

### Trusted Inputs
Versioned, checked-in, human-authored:
- `data/resume.txt` — Josh's resume (parser-compatible format)
- `src/models/schema.sql` / `schema_postgres.sql` — DDL for 13 tables
- Pydantic model definitions in `src/models/entities.py`
- Tier strategy configuration (Tier 1/2/3 company classification)
- Test fixtures (`tests/mocks/linkedin_search_page.html`, `linkedin_job_detail.html`)

### Untrusted Inputs
External or LLM-generated, must be validated before use:
- Scraped job listing HTML from LinkedIn
- Claude API JSON responses (scores, tailored bullets, cover letter text)
- Vertex AI classification responses
- User-submitted URLs via the web UI

### Context-Locked State
Data produced from mixed inputs whose trust holds only within its creation context:
- `tailored_bullets` records — valid for the specific job + resume + tier combination that produced them
- `applications` records — state machine transitions bound to specific job listings
- LLM fit scores — valid for the prompt version and model version that produced them

---

## Authority Boundaries

### What Automation May Do
- Parse, normalize, and score job listings
- Rewrite resume bullets (subject to Semantic Fidelity Guardrail v1.1)
- Generate cover letter drafts
- Pre-fill application form fields
- Queue applications for review

### What Automation May Not Do
- Submit applications without human approval (approval queue enforced)
- Override the Semantic Fidelity Guardrail (hallucinated metrics are rejected)
- Promote a score > 1.0 or < 0.0 into the database
- Bypass Pydantic validation at module boundaries
- Modify schema.sql without also updating schema_postgres.sql

### What Requires Human Authority
- Final approval of auto-apply submissions
- Tier strategy decisions (which companies to target)
- Resume content accuracy (real metrics, real experience)
- Go/no-go on cover letter content before PDF generation

---

## Trust Validation Mechanisms

| Component | Trust Level | Validation Mechanism |
|-----------|------------|---------------------|
| Scraped HTML | Untrusted | Normalizer strips tags, extracts structured fields |
| LLM fit score | Untrusted | Pydantic validates 0.0–1.0 bounds, JSON parsing |
| LLM tailored bullet | Untrusted | Semantic Fidelity Guardrail v1.1 rejects drift/hallucination |
| LLM cover letter | Untrusted | Pydantic CoverLetterData model validates structure |
| Vertex AI tier | Untrusted | Fail-open design — classification failure returns None, pipeline continues |
| Resume text | Trusted | Human-authored, checked into `data/resume.txt` |
| Database records | Trusted | Idempotent writes, ON CONFLICT deduplication |
| ATS prefill values | Trusted | Deterministic extraction from validated DB records |
| PDF output | Trusted | Deterministic rendering from validated Pydantic models |

---

## Enrichment vs. Core Distinction

**Enrichment fails open** — if it breaks, the pipeline continues without it:
- Vertex AI regime classification (optional, returns None on failure)
- Skill gap analysis (informational, not blocking)

**Core fails closed** — if it breaks, the pipeline stops:
- Pydantic validation at boundaries (malformed data rejected)
- LLM score parsing (unparseable response → job not ranked)
- Semantic Fidelity Guardrail (hallucinated content → bullet rejected)
- Database writes (constraint violations → transaction rolled back)

---

## Related Files

- `src/models/entities.py` — Pydantic v2 models (structural trust enforcement)
- `src/ranker/llm_ranker.py` — Claude API scoring with response validation
- `src/tailoring/engine.py` — Semantic Fidelity Guardrail v1.1
- `src/apply/prefill.py` — Deterministic ATS prefill (no LLM involvement)
- `docs/ai-onboarding/RULES.md` — Anti-hallucination rules and conventions
- `docs/ai-onboarding/PROJECT_CONTEXT.md` — Full architecture reference
