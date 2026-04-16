# Céal Deep Work Session — Monday, March 30, 2026
## 2:00 PM – 5:00 PM ET (3-Hour Time Box)

---

## Objective

**Stand up GitHub Actions CI/CD enforcing lint + test gates, then scaffold the Phase 2 (Resume Tailoring) module structure with Pydantic v2 data contracts — shipping a green pipeline and importable Phase 2 skeleton by 5:00 PM.**

---

## Personas Tagged In

| Role | Persona | Mandate |
|------|---------|---------|
| **Lead** | Lead Backend Python Engineer (QA & Reliability) | Enforce CI gate that blocks merge on any lint or test failure. Scaffold Phase 2 files with strict Pydantic v2 boundaries. Zero regressions to the existing 93 tests. |
| **Supporting** | DevOps / Infrastructure Engineer | Own the GitHub Actions workflow YAML — matrix strategy, caching, artifact upload. Ensure the pipeline runs in < 2 minutes. |
| **Supporting** | Data Product Manager | Validate that every new file and model maps to a Phase 2 deliverable. Block scope creep. Frame session output as a resume bullet. |

---

## Time-Blocked Intervals

### 2:00 PM – 2:45 PM | CI/CD Pipeline Setup (45 min)
**[DevOps Engineer leaning in, Backend Engineer reviewing]**

GitHub Actions workflow that gates every push and PR to `main`.

- [ ] Create `.github/workflows/ci.yml` with matrix: Python 3.11 + 3.12
- [ ] **Stage 1 — Lint:** `ruff check src/ tests/` (fail-fast: true)
- [ ] **Stage 2 — Unit Tests:** `pytest tests/unit/ -v --tb=short` (depends on lint)
- [ ] **Stage 3 — Integration Tests:** `pytest tests/integration/ -v --tb=short` (depends on unit)
- [ ] **Stage 4 — Coverage:** `pytest --cov=src --cov-report=term-missing --cov-fail-under=80`
- [ ] Add `pip` dependency caching (`actions/cache` on `requirements.txt` hash)
- [ ] Add status badge to `README.md`
- [ ] **Constraint Check:** Ensure `ruff` config enforces the rules already passing locally (no new warnings)
- [ ] **TDD Gate:** Push to a feature branch, confirm all 93 tests pass in CI before moving on

### 2:45 PM – 3:45 PM | Phase 2 Data Model Design & Scaffolding (60 min)
**[Backend Engineer leaning in, DPM validating scope]**

Create the file structure and Pydantic v2 models that Phase 2 will be built on top of all week.

- [ ] Create `src/tailoring/__init__.py` (new subpackage)
- [ ] Create `src/tailoring/models.py` — Phase 2 Pydantic schemas:
  - `ResumeSection` — enum: SUMMARY, EXPERIENCE, SKILLS, PROJECTS, CERTIFICATIONS
  - `ParsedBullet` — section, original_text, skills_referenced: List[str], metrics: Optional[str]
  - `ParsedResume` — profile_id, sections: Dict[ResumeSection, List[ParsedBullet]], raw_text
  - `SkillGap` — skill_name, category, job_requires: bool, resume_has: bool, proficiency: Optional[Proficiency]
  - `TailoringRequest` — job_id, profile_id, target_tier: int (1-3), emphasis_areas: List[str]
  - `TailoredBullet` — original: ParsedBullet, rewritten_text, xyz_format: bool, relevance_score: float (0.0-1.0)
  - `TailoringResult` — request: TailoringRequest, tailored_bullets: List[TailoredBullet], skill_gaps: List[SkillGap], tailoring_version: str
- [ ] **Constraint Check:** Every model uses Pydantic v2 `model_validator` or `field_validator` where business rules apply (e.g., relevance_score 0.0–1.0, target_tier 1–3)
- [ ] **Constraint Check:** Model hierarchy enforces boundary: raw resume text → `ParsedResume` → `TailoringResult` (no skipping steps)
- [ ] Create `src/tailoring/resume_parser.py` — stub class `ResumeProfileParser` with:
  - `parse(raw_text: str) -> ParsedResume` (raises NotImplementedError for now)
- [ ] Create `src/tailoring/skill_extractor.py` — stub class `SkillOverlapAnalyzer` with:
  - `analyze(parsed_resume: ParsedResume, job_skills: List[Skill]) -> List[SkillGap]` (stub)
- [ ] Create `src/tailoring/engine.py` — stub class `TailoringEngine` with:
  - `tailor(request: TailoringRequest) -> TailoringResult` (stub, will use Claude API Wed/Thu)
- [ ] Wire `__init__.py` exports: `from .models import *`, `from .resume_parser import ResumeProfileParser`, etc.

### 3:45 PM – 4:30 PM | Test Scaffolding + Model Validation Tests (45 min)
**[Backend Engineer + QA Lead leaning in]**

TDD: write the tests for the new models BEFORE anyone implements logic this week.

- [ ] Create `tests/unit/test_tailoring_models.py` with at least these cases:
  - `test_parsed_bullet_valid` — happy path
  - `test_parsed_bullet_empty_text_rejected` — min_length enforcement
  - `test_tailored_bullet_score_bounds` — relevance_score rejects < 0.0 and > 1.0
  - `test_tailoring_request_tier_bounds` — target_tier rejects 0 and 4
  - `test_skill_gap_construction` — round-trip serialization
  - `test_parsed_resume_section_enum` — invalid section key rejected
  - `test_tailoring_result_version_required` — tailoring_version cannot be empty
- [ ] Create `tests/unit/test_resume_parser.py` with stub test:
  - `test_parser_raises_not_implemented` — confirms stub behavior
- [ ] Create `tests/unit/test_skill_extractor.py` with stub test:
  - `test_analyzer_raises_not_implemented` — confirms stub behavior
- [ ] **TDD Gate:** Run full suite locally — target: 97 existing + ~10 new = **107+ tests, all green**
- [ ] **Constraint Check:** All test files use `pytest.mark.asyncio` where applicable, frozen fixtures (no live API calls)

### 4:30 PM – 4:45 PM | Integration Verification (15 min)
**[DevOps Engineer leaning in]**

- [ ] Push Phase 2 scaffold to feature branch (`feature/phase2-scaffold`)
- [ ] Confirm CI pipeline runs: lint → unit → integration → coverage
- [ ] All 107+ tests pass in GitHub Actions
- [ ] No regressions to existing Phase 1 functionality
- [ ] Coverage stays ≥ 80%

### 4:45 PM – 5:00 PM | Career Translation & Session Close (15 min)
**[Data Product Manager + Career Strategist leaning in]**

- [ ] Tag release: `v1.1.0-phase2-scaffold`
- [ ] Update README.md Phase 2 section with new module descriptions
- [ ] Draft X-Y-Z resume bullet (see below)
- [ ] Identify Tuesday's first task (likely: implement `ResumeProfileParser.parse()` with Claude API)

---

## Deliverables — What Ships by 5:00 PM

### Code Artifacts
| File | Purpose | Status |
|------|---------|--------|
| `.github/workflows/ci.yml` | CI/CD pipeline (lint + test + coverage) | New |
| `src/tailoring/__init__.py` | Phase 2 subpackage | New |
| `src/tailoring/models.py` | 7 Pydantic v2 data contracts | New |
| `src/tailoring/resume_parser.py` | `ResumeProfileParser` stub | New |
| `src/tailoring/skill_extractor.py` | `SkillOverlapAnalyzer` stub | New |
| `src/tailoring/engine.py` | `TailoringEngine` stub | New |
| `tests/unit/test_tailoring_models.py` | ~7 model validation tests | New |
| `tests/unit/test_resume_parser.py` | Parser stub test | New |
| `tests/unit/test_skill_extractor.py` | Extractor stub test | New |
| `README.md` | CI badge + Phase 2 module docs | Updated |

### Strategic Alignment
**Tier 1 — Apply Now (Technical Solutions Engineer / TPM)**
This session directly demonstrates CI/CD pipeline design, test-driven development, and schema-first architecture — core competencies for TSE roles at Stripe, Datadog, and Coinbase. The Pydantic data contracts show production-grade data validation, and the GitHub Actions workflow shows DevOps fluency.

**Tier 2 — Build Credential (Cloud Solutions Architect / DevOps Engineer)**
The CI/CD pipeline is an infrastructure artifact. When we containerize Céal next month (Docker + GCP Cloud Run), this workflow becomes the foundation of a full CI/CD → CD pipeline — a direct talking point for cloud roles.

### Google X-Y-Z Resume Bullet
> **Engineered a CI/CD pipeline achieving 100% test gate enforcement across 107+ automated tests, by implementing GitHub Actions with matrix builds, ruff linting, and pytest coverage thresholds for an async ETL career signal engine.**

---

## Architectural Constraints (Standing Orders)

These apply to every task above:

1. **Pydantic v2 Boundaries** — Data must flow through the model hierarchy. No raw dicts cross module boundaries.
2. **Idempotent Operations** — Any new DB operations must use `ON CONFLICT` upserts.
3. **TDD** — Test files scaffold before or alongside implementation. No untested code merges.
4. **Zero Regression** — The existing 93 tests must remain green at every commit.
5. **Systemic Problem Solving** — We are designing architecture, not "vibe coding." Every stub has a docstring explaining its future role and the data contract it will fulfill.

---

*Session prepared by: Technical Program Manager persona*
*Stakeholders present: Lead Backend Python Engineer (Lead), DevOps Engineer, Data Product Manager, Career Strategist*
