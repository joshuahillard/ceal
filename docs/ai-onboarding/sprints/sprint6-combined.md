# CLAUDE_CODE_SPRINT6_GAPFILL.md

**Sprint 6 — Gap-Fill: Semantic Validation, Database Test Coverage, Pre-Fill Hardening**

**Persona:** QA Lead (primary), AI Architect, Backend Engineer
**Branch:** `main`
**Expected HEAD:** Post-Sprint 5 with PostgreSQL dialect fixes applied
**Expected test count at start:** 217 passing
**Expected test count at end:** 245+
**Sprint objective:** Close every testing blind spot and trust gap identified during Sprints 1–5 stakeholder review. No new features — hardening only.

---

## CONTEXT BLOCK

### What has shipped (Sprints 1–5, April 2 2026)

| Sprint | Scope | Commit | Tests After |
|--------|-------|--------|-------------|
| 1 | FastAPI + Jinja2 UI (Dashboard, Jobs, Demo) | `655132f` | 167 |
| 2 | Phase 3 CRM: Kanban board, state machine, reminders, prompt v1.1 | `92c0894` | 179 |
| 3 | Phase 4 Auto-Apply: pre-fill engine, approval queue, docs overhaul | `7a4adf5` | 202 |
| 4 | Docker containerization, GCP Cloud Run deployment, health endpoint | `15609f5` | 204 |
| 5 | Cloud SQL (PostgreSQL) polymorphic database layer | `286ab51` | 217 |

### Known gaps from stakeholder review

1. **Mock blind spot** — Web route tests mock `get_jobs_by_status()`, `get_application_summary()`, `get_stale_applications()`, `get_approval_queue()`, `get_application_stats()` at the route layer. The actual SQL is never exercised. This is the same class of bug that caused the Jobs tab to break 3 times.
2. **Semantic truthfulness** — The tailoring engine validates output *structure* (X-Y-Z format, score bounds, proficiency mapping) but not *meaning*. Sprint 2 documented the GCP keyword-stuffing problem: "Josh never used GCP at Toast." Prompt v1.1 added anti-keyword-stuffing rules, but there is no programmatic check that rewritten bullets don't fabricate tools, inflate metrics, or invent company references.
3. **Pre-fill engine untested against realistic data** — The 16-field ATS regex in `src/apply/prefill.py` has unit tests for the extraction logic, but no test validates extraction against realistic, messy ATS form field patterns.
4. **PostgreSQL dialect fixes need commit/push verification** — Session notes state: "Fixes applied locally. Needs commit + push + CI verification." Three fixes: dollar-quoting in `_split_sql_statements()`, CREATE TRIGGER mode detection, `ROUND(double precision)` → `CAST(AVG(...) AS numeric)`.

---

## PRE-FLIGHT CHECK (Task 0)

Run these commands BEFORE any code changes. If any check fails, STOP and report.

```bash
cd /path/to/ceal
echo "=== Pre-flight ==="
python -m pytest tests/ -q 2>&1 | tail -5
ruff check src/ tests/ 2>&1 | tail -3
git status
git log --oneline -5
echo "=== Checking for uncommitted dialect fixes ==="
git diff --name-only
git diff --cached --name-only
```

**Expected results:**
- 217+ tests passing
- ruff clean (0 errors)
- Branch: `main`
- `git diff` may show uncommitted changes to `src/models/database.py` (PostgreSQL dialect fixes from post-Sprint 5)

**Conditional: If uncommitted dialect fixes exist:**
```bash
git add src/models/database.py
git commit -m "fix(db): PostgreSQL dialect compatibility — dollar-quoting, trigger mode, ROUND cast"
git push origin main
```
Wait for CI to pass before proceeding. Verify with:
```bash
gh run list --limit 1
```

---

## ANTI-HALLUCINATION RULES

1. **READ before WRITE.** Every TASK that modifies an existing file starts with `Read first:` — you MUST read the specified file and verify the function/class exists before editing.
2. **No hallucinated imports.** Only import modules that exist in the codebase or in `requirements.txt`.
3. **No hallucinated function signatures.** If a task references a function, verify its actual signature by reading the source file first.
4. **No secrets in committed files.** Never hardcode API keys, database passwords, or credentials.
5. **Preserve existing tests.** No existing test may be deleted or modified to pass. New tests only.
6. **No dialect-specific SQL.** (Rule 13 from Sprint 5) All new SQL must work on both SQLite and PostgreSQL.
7. **Dual-backend testing.** (Rule 14 from Sprint 5) Database-level tests must exercise real SQL, not mocks.
8. **Fail loudly.** If a validation or test cannot be implemented as described, STOP and explain why. Do not silently skip.
9. **Match existing patterns.** New test files must follow the same class/fixture/assertion patterns as existing test files in `tests/unit/`.
10. **Semantic validator must be deterministic.** The `SemanticValidator` must use string matching and regex — no LLM calls inside the validator. The validator validates LLM output; it cannot itself depend on an LLM.

---

## EXPLICIT FILE INVENTORY

### Files to READ (verify these exist before referencing)

| File | Key contents to verify |
|------|----------------------|
| `src/models/database.py` | `get_jobs_by_status()`, `get_application_summary()`, `get_stale_applications()`, `update_job_status()`, `VALID_TRANSITIONS`, `create_application()`, `get_approval_queue()`, `get_application_stats()`, `update_application_status()` |
| `src/tailoring/engine.py` | `TailoringEngine`, `generate_tailored_profile()`, `_parse_llm_response()`, `_SYSTEM_PROMPT`, `_TIER_PROMPTS`, `CURRENT_PROMPT_VERSION` (should be `"v1.1"`) |
| `src/tailoring/models.py` | `TailoredBullet` (fields: `original`, `rewritten_text`, `xyz_format`, `relevance_score`), `TailoringResult`, `SkillGap`, `TailoringRequest` |
| `src/tailoring/resume_parser.py` | `SKILL_TAXONOMY` dict (~67 canonical skills), `ResumeProfileParser` |
| `src/apply/prefill.py` | 16 ATS field extraction functions, confidence scoring logic |
| `tests/unit/test_database.py` | `TestCoreQuerySQL` class (9 tests — the pattern to follow for new DB tests) |
| `tests/unit/test_tailoring_engine.py` | `TestTailoringEngine` class (frozen LLM response pattern) |
| `tests/unit/test_tailoring_models.py` | Pydantic validation test patterns |

### Files to CREATE

| File | Purpose |
|------|---------|
| `src/tailoring/validators.py` | SemanticValidator — entity extraction + rewrite truthfulness checks |
| `tests/unit/test_semantic_validator.py` | Validator unit tests |
| `tests/unit/test_prefill_validation.py` | Pre-fill engine validation against realistic ATS patterns |

### Files to MODIFY

| File | Changes |
|------|---------|
| `tests/unit/test_database.py` | Add `TestCRMQuerySQL` and `TestAutoApplyQuerySQL` classes |
| `src/tailoring/engine.py` | Wire SemanticValidator into `generate_tailored_profile()`, bump `CURRENT_PROMPT_VERSION` to `"v1.2"`, update `_SYSTEM_PROMPT` |
| `README.md` | Add semantic validation docs, update test count |

---

## TASKS

### TASK 1: Tag rollback point

```bash
git tag v2.5.1-pre-sprint6
git push origin v2.5.1-pre-sprint6
```

---

### TASK 2: Database-level tests for CRM queries

**Read first:** `src/models/database.py` — find `get_jobs_by_status()`, `get_application_summary()`, `get_stale_applications()`, `update_job_status()`, `VALID_TRANSITIONS`. Note their exact signatures, parameters, and return types.

**Read first:** `tests/unit/test_database.py` — find `TestCoreQuerySQL`. Note the fixture pattern (how the test database is set up, how `init_db()` is called, how test data is inserted).

**Add** a new class `TestCRMQuerySQL` to `tests/unit/test_database.py` following the exact same fixture pattern as `TestCoreQuerySQL`.

**Required test methods:**

```python
class TestCRMQuerySQL:
    """Database-level tests for CRM query functions — exercises real SQL, no mocks."""

    async def test_get_jobs_by_status_returns_only_matching(self):
        """Insert jobs with different statuses. Query for 'applied'. Only applied jobs returned."""

    async def test_get_jobs_by_status_empty_result(self):
        """Query for a status with no matching jobs. Returns empty list."""

    async def test_get_application_summary_counts_by_status(self):
        """Insert jobs across multiple statuses. Summary counts match expected."""

    async def test_get_stale_applications_respects_threshold(self):
        """Insert applications with varying ages. Only those older than threshold returned."""

    async def test_get_stale_applications_excludes_terminal_states(self):
        """Jobs in terminal states (offered, rejected, archived) are NOT returned as stale."""

    async def test_update_job_status_valid_transition(self):
        """Transition a job from 'ranked' to 'applied'. Status updates in DB."""

    async def test_update_job_status_invalid_transition_rejected(self):
        """Attempt invalid transition (e.g., 'scraped' to 'offered'). Raises or returns error."""

    async def test_update_job_status_adds_note(self):
        """Transition with a note. Note is persisted."""
```

**Verification:**
```bash
python -m pytest tests/unit/test_database.py::TestCRMQuerySQL -v
ruff check tests/unit/test_database.py
```

---

### TASK 3: Database-level tests for auto-apply queries

**Read first:** `src/models/database.py` — find `create_application()`, `get_approval_queue()`, `get_application_stats()`, `update_application_status()`. Note their exact signatures.

**Read first:** `tests/unit/test_database.py` — reuse the same fixture pattern.

**Add** a new class `TestAutoApplyQuerySQL` to `tests/unit/test_database.py`.

**Required test methods:**

```python
class TestAutoApplyQuerySQL:
    """Database-level tests for auto-apply query functions — exercises real SQL, no mocks."""

    async def test_create_application_returns_id(self):
        """Create an application. Returns valid integer ID."""

    async def test_create_application_links_to_job(self):
        """Created application references the correct job_id."""

    async def test_get_approval_queue_returns_pending_only(self):
        """Insert applications with mixed statuses. Queue returns only pending."""

    async def test_get_approval_queue_empty_when_none_pending(self):
        """No pending applications. Returns empty list."""

    async def test_get_application_stats_counts_all_statuses(self):
        """Stats reflect correct counts per status."""

    async def test_update_application_status_valid(self):
        """Update application from 'pending' to 'approved'. Status persists."""

    async def test_update_application_status_preserves_fields(self):
        """Status update does not corrupt pre-filled field data."""
```

**Verification:**
```bash
python -m pytest tests/unit/test_database.py::TestAutoApplyQuerySQL -v
ruff check tests/unit/test_database.py
```

---

### TASK 4: Pre-fill engine validation tests

**Read first:** `src/apply/prefill.py` — find all field extraction functions, the 16 ATS field definitions, confidence scoring logic. Note the exact function signatures and field names.

**Read first:** `tests/unit/test_autoapply.py` — note existing test patterns to avoid duplication.

**Create** `tests/unit/test_prefill_validation.py`:

```python
"""
Pre-fill engine validation — tests extraction against realistic, messy ATS field patterns.
Closes the gap between unit-tested regex and real-world form data.
"""

class TestPrefillRealisticExtraction:
    """Validate pre-fill extraction against patterns seen in real ATS systems."""

    def test_full_name_various_formats(self):
        """Extract name from: 'John Smith', 'Smith, John', 'John A. Smith'."""

    def test_email_standard_and_plus_addressing(self):
        """Extract: 'user@domain.com', 'user+tag@domain.com'."""

    def test_phone_us_formats(self):
        """Extract: '(555) 123-4567', '555-123-4567', '+1 555 123 4567', '5551234567'."""

    def test_linkedin_url_variations(self):
        """Extract from full URL, mobile URL, vanity URL with trailing slash."""

    def test_address_multiline_and_single_line(self):
        """Extract from: '123 Main St\\nBoston, MA 02101' and '123 Main St, Boston, MA 02101'."""

    def test_empty_fields_return_none_not_error(self):
        """Empty or whitespace-only input returns None with zero confidence."""

    def test_malformed_email_low_confidence(self):
        """'user@' or 'user@.com' returns low confidence, not crash."""

    def test_confidence_scores_within_bounds(self):
        """All confidence scores are 0.0–1.0 regardless of input quality."""

    def test_international_phone_formats(self):
        """'+44 20 7946 0958', '+91-9876543210' — non-US formats handled."""

    def test_all_16_fields_extractable(self):
        """Provide a complete, well-formed resume profile. All 16 fields extracted with confidence > 0.5."""
```

**Verification:**
```bash
python -m pytest tests/unit/test_prefill_validation.py -v
ruff check tests/unit/test_prefill_validation.py
```

---

### TASK 5: Semantic truthfulness validator

**Read first:** `src/tailoring/models.py` — find `TailoredBullet` fields (`original`, `rewritten_text`, `relevance_score`).

**Read first:** `src/tailoring/resume_parser.py` — find `SKILL_TAXONOMY` dict and `_METRIC_PATTERN` regex.

**Create** `src/tailoring/validators.py`:

```python
"""
Semantic truthfulness validator for tailored resume bullets.

Validates that LLM-rewritten bullets do not fabricate tools, inflate metrics,
or reference companies/skills not present in the candidate's actual resume.

Design principle: This validator is DETERMINISTIC — no LLM calls.
It uses string matching, regex, and set comparison against known resume content.
"""
import re
import structlog
from dataclasses import dataclass, field

logger = structlog.get_logger()


@dataclass
class ValidationResult:
    """Result of semantic validation for a single rewritten bullet."""
    is_valid: bool
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class SemanticValidator:
    """
    Validates that rewritten resume bullets are semantically faithful
    to the original text and the candidate's known skill set.
    """

    def __init__(self, resume_skills: list[str], skill_taxonomy: dict[str, list[str]]):
        """
        Args:
            resume_skills: Canonical skill names the candidate actually has.
            skill_taxonomy: The SKILL_TAXONOMY dict from resume_parser.py.
        """
        # Build the implementation here

    def validate_bullet(self, original: str, rewritten: str) -> ValidationResult:
        """
        Compare original bullet to rewritten version.

        Checks:
        1. Fabricated tools/technologies — tools in rewrite not in resume_skills
        2. Metric inflation — numeric values in rewrite significantly larger than originals
        3. Fabricated qualifiers — team sizes, dollar amounts, percentages not in original
        4. Preserved factual anchors — key metrics from original appear in rewrite
        """
        # Implementation here

    def validate_batch(self, bullets: list[tuple[str, str]]) -> list[ValidationResult]:
        """Validate a list of (original, rewritten) bullet pairs."""
        return [self.validate_bullet(orig, rewrite) for orig, rewrite in bullets]

    def _extract_tools(self, text: str) -> set[str]:
        """Extract technology/tool references from text using skill_taxonomy."""
        # Cross-reference against taxonomy

    def _extract_metrics(self, text: str) -> list[dict]:
        """
        Extract numeric metrics from text.
        Returns list of dicts: {'value': float, 'unit': str, 'raw': str}
        Examples: '$12M' → {'value': 12000000, 'unit': 'dollars', 'raw': '$12M'}
                  '37%'  → {'value': 37, 'unit': 'percent', 'raw': '37%'}
                  'team of 5' → {'value': 5, 'unit': 'count', 'raw': 'team of 5'}
        """
        # Reuse _METRIC_PATTERN from resume_parser.py or define compatible pattern

    def _check_metric_inflation(self, original_metrics: list[dict], rewritten_metrics: list[dict]) -> list[str]:
        """
        Flag metrics in rewrite that are significantly inflated vs original.
        Threshold: rewrite metric > 1.5x original metric with same unit → violation.
        New metrics not in original at all → violation.
        """

    def _check_fabricated_tools(self, rewritten_tools: set[str], resume_skills: set[str]) -> list[str]:
        """
        Flag tools/technologies in the rewrite that are NOT in the candidate's
        known skill set. This is the "GCP at Toast" check.
        """
```

**Key design decisions:**
- The validator MUST NOT call any LLM. It is deterministic.
- It reuses the `SKILL_TAXONOMY` from `resume_parser.py` for tool detection — do NOT create a separate taxonomy.
- Metric extraction pattern should be compatible with `_METRIC_PATTERN` from `resume_parser.py`.
- `violations` = hard failures (fabricated tools, inflated metrics). `warnings` = soft flags (rephrased but factually equivalent).
- A bullet with any `violations` has `is_valid = False`. A bullet with only `warnings` has `is_valid = True`.

**Verification:**
```bash
python -c "from src.tailoring.validators import SemanticValidator, ValidationResult; print('Import OK')"
ruff check src/tailoring/validators.py
```

---

### TASK 6: Semantic validator unit tests

**Read first:** `tests/unit/test_tailoring_engine.py` — note frozen response test patterns.

**Read first:** `src/tailoring/validators.py` — verify the actual class/method signatures from Task 5.

**Create** `tests/unit/test_semantic_validator.py`:

```python
"""
Semantic truthfulness validator tests.

Tests the deterministic validation layer that catches LLM fabrication,
metric inflation, and tool hallucination in rewritten resume bullets.
"""

class TestSemanticValidatorToolCheck:
    """Validates detection of fabricated tool/technology references."""

    def test_faithful_rewrite_passes(self):
        """Original: 'Managed payment systems using Python and REST APIs'
           Rewrite:  'Directed payment processing platform leveraging Python-based REST API integrations'
           resume_skills includes Python, REST APIs, Payment Processing.
           → is_valid=True, no violations."""

    def test_fabricated_tool_detected(self):
        """Original: 'Managed escalation workflows for enterprise clients'
           Rewrite:  'Managed escalation workflows using GCP-based incident management systems'
           resume_skills does NOT include GCP.
           → is_valid=False, violation mentions 'GCP'."""

    def test_fabricated_tool_from_taxonomy(self):
        """Rewrite introduces 'Kubernetes' — present in SKILL_TAXONOMY but NOT in resume_skills.
           → is_valid=False."""

    def test_tool_in_resume_skills_passes(self):
        """Rewrite mentions 'Docker' — Docker IS in resume_skills.
           → is_valid=True."""

    def test_multiple_fabricated_tools(self):
        """Rewrite introduces both 'AWS' and 'Terraform' — neither in resume_skills.
           → is_valid=False, two violations."""


class TestSemanticValidatorMetricCheck:
    """Validates detection of inflated or fabricated numeric claims."""

    def test_preserved_metric_passes(self):
        """Original: 'Reduced costs by 37%'. Rewrite: 'Achieved 37% cost reduction'.
           → is_valid=True."""

    def test_inflated_metric_detected(self):
        """Original: 'Managed team of 5'. Rewrite: 'Led cross-functional team of 15'.
           → is_valid=False, violation flags metric inflation (5 → 15)."""

    def test_inflated_dollar_amount_detected(self):
        """Original: 'Saved $500K annually'. Rewrite: 'Drove $2M in annual savings'.
           → is_valid=False."""

    def test_new_metric_not_in_original_flagged(self):
        """Original: 'Improved deployment process'. Rewrite: 'Improved deployment process, reducing downtime by 99.9%'.
           Original has no percentage. Rewrite introduces '99.9%'.
           → is_valid=False, violation flags fabricated metric."""

    def test_minor_rounding_allowed(self):
        """Original: '$12.3M'. Rewrite: '$12M'. Within tolerance.
           → is_valid=True (or warning, not violation)."""


class TestSemanticValidatorEdgeCases:
    """Edge cases and integration scenarios."""

    def test_empty_original_handled(self):
        """Empty original text does not crash. Returns valid with warning."""

    def test_empty_rewrite_handled(self):
        """Empty rewrite text does not crash."""

    def test_no_metrics_in_either_passes(self):
        """Neither original nor rewrite contain metrics. Passes."""

    def test_batch_validation(self):
        """validate_batch() processes multiple bullets, returns list of results."""

    def test_case_insensitive_tool_matching(self):
        """'python' in text matches 'Python' in resume_skills."""

    def test_tool_aliases_matched(self):
        """'REST API' in SKILL_TAXONOMY has aliases ['rest api', 'restful', 'api integration'].
           Rewrite using 'RESTful' matches if resume has 'REST APIs'."""
```

**Verification:**
```bash
python -m pytest tests/unit/test_semantic_validator.py -v
ruff check tests/unit/test_semantic_validator.py
```

---

### TASK 7: Wire SemanticValidator into TailoringEngine

**Read first:** `src/tailoring/engine.py` — find `generate_tailored_profile()` method. Identify the exact point between `_parse_llm_response()` and `TailoringResult` construction where validation should be inserted.

**Read first:** `src/tailoring/resume_parser.py` — find `SKILL_TAXONOMY` import path.

**Modify** `src/tailoring/engine.py`:

1. Import `SemanticValidator` and `ValidationResult` from `src.tailoring.validators`
2. Import `SKILL_TAXONOMY` from `src.tailoring.resume_parser`
3. In `generate_tailored_profile()`, after parsing LLM response and before constructing `TailoringResult`:

```python
# --- Semantic truthfulness validation ---
validator = SemanticValidator(
    resume_skills=[sg.skill_name for sg in skill_gaps if sg.resume_has],
    skill_taxonomy=SKILL_TAXONOMY,
)

validated_bullets = []
for bullet in tailored_bullets:
    result = validator.validate_bullet(bullet.original, bullet.rewritten_text)
    if result.is_valid:
        validated_bullets.append(bullet)
    else:
        logger.warning(
            "semantic_validation_failed",
            original=bullet.original[:80],
            rewritten=bullet.rewritten_text[:80],
            violations=result.violations,
        )
        # Fallback: keep original text with zero relevance score
        validated_bullets.append(
            TailoredBullet(
                original=bullet.original,
                rewritten_text=bullet.original,  # preserve original
                xyz_format=False,
                relevance_score=0.0,
            )
        )
```

4. Use `validated_bullets` (not `tailored_bullets`) when constructing the final `TailoringResult`.

**Critical:** Do NOT remove or bypass existing Pydantic validation. The SemanticValidator is an ADDITIONAL layer that runs AFTER Pydantic structural validation passes.

**Verification:**
```bash
python -m pytest tests/unit/test_tailoring_engine.py -v
ruff check src/tailoring/engine.py
```

---

### TASK 8: Prompt v1.2 — anti-fabrication constraint

**Read first:** `src/tailoring/engine.py` — find `_SYSTEM_PROMPT` and `CURRENT_PROMPT_VERSION`.

**Modify** `src/tailoring/engine.py`:

1. Bump `CURRENT_PROMPT_VERSION` from `"v1.1"` to `"v1.2"`

2. Append the following rule to `_SYSTEM_PROMPT` (add to the existing rules section, do not replace existing rules):

```
- NEVER reference tools, technologies, platforms, or frameworks not present in the candidate's resume text. You may rephrase and reframe existing experience, but you must not fabricate tool usage. Example violation: adding "using GCP" when the candidate's resume does not mention GCP.
- NEVER inflate numeric metrics. If the original says "team of 5", the rewrite must say "team of 5" — not "team of 15". Preserve all dollar amounts, percentages, and counts exactly as stated in the original bullet.
- NEVER fabricate company names, client names, or project names not present in the original text.
```

3. Verify `_TIER_PROMPTS` do not contradict these rules. Specifically check that Tier 1 and Tier 3 prompts do not instruct Claude to "add" or "emphasize" tools the candidate doesn't have.

**Verification:**
```bash
python -c "from src.tailoring.engine import CURRENT_PROMPT_VERSION; assert CURRENT_PROMPT_VERSION == 'v1.2', f'Expected v1.2, got {CURRENT_PROMPT_VERSION}'"
ruff check src/tailoring/engine.py
```

---

### TASK 9: Update tailoring engine tests for validator integration

**Read first:** `tests/unit/test_tailoring_engine.py` — find `TestTailoringEngine` class and the frozen LLM response fixtures.

**Modify** `tests/unit/test_tailoring_engine.py`:

Add test methods to `TestTailoringEngine` (or a new `TestTailoringEngineWithValidator` class):

```python
async def test_engine_rejects_fabricated_tool_in_bullet(self):
    """Frozen LLM response includes a bullet with 'using GCP'.
       Resume skills do NOT include GCP.
       Engine should replace rewritten_text with original text and set relevance_score=0.0."""

async def test_engine_passes_faithful_rewrite(self):
    """Frozen LLM response with faithful rewrite (tools match resume skills).
       Engine passes bullet through unchanged."""

async def test_engine_logs_semantic_violation(self):
    """Verify structlog captures the semantic_validation_failed event."""
```

**Verification:**
```bash
python -m pytest tests/unit/test_tailoring_engine.py -v
ruff check tests/unit/test_tailoring_engine.py
```

---

### TASK 10: README update

**Read first:** `README.md`

**Modify** `README.md`:

1. Add a new section under the tailoring engine documentation:

```markdown
### Semantic Validation Layer (Sprint 6)

All LLM-rewritten bullets pass through a deterministic SemanticValidator before entering
the database. The validator checks for:

- **Fabricated tools/technologies** — flags any tool in the rewrite not present in the
  candidate's verified skill set (cross-referenced against SKILL_TAXONOMY)
- **Metric inflation** — detects when numeric values (dollar amounts, percentages, team
  sizes) are inflated beyond the original resume text
- **Fabricated qualifiers** — catches invented metrics, company names, or project
  references not present in the source material

Bullets that fail validation are replaced with the original text and logged for review.
The validator is deterministic (no LLM calls) and adds ~0ms latency per bullet.
```

2. Update the test count to reflect the final number after this sprint.

3. Update the version reference to v1.2 for the prompt version.

**Verification:**
```bash
ruff check README.md 2>/dev/null || true  # README is markdown, ruff won't lint it — just verify it exists
head -20 README.md
```

---

### TASK 11: Update `src/tailoring/__init__.py` exports

**Read first:** `src/tailoring/__init__.py` — verify current exports.

**Modify** to add the new public exports:

```python
from src.tailoring.validators import SemanticValidator, ValidationResult
```

Add `SemanticValidator` and `ValidationResult` to the `__all__` list if one exists.

**Verification:**
```bash
python -c "from src.tailoring import SemanticValidator, ValidationResult; print('Export OK')"
```

---

### TASK 12: Final verification — lint, test, commit, tag

```bash
# 1. Lint
ruff check src/ tests/

# 2. Full test suite
python -m pytest tests/ -v 2>&1 | tail -20

# 3. Coverage check
python -m pytest tests/ --cov=src --cov-report=term-missing --cov-fail-under=80 2>&1 | tail -10

# 4. Verify test count increased
python -m pytest tests/ -q 2>&1 | grep "passed"
# Expected: 245+ passed

# 5. Commit
git add -A
git status  # Review — no secrets, no .env, no data/*.db
git commit -m "feat(validation): Sprint 6 — semantic truthfulness validator, DB test coverage, pre-fill hardening

- Add SemanticValidator: deterministic tool/metric fabrication detection
- Wire validator into TailoringEngine (additional layer after Pydantic)
- Bump prompt to v1.2 with anti-fabrication constraints
- Add TestCRMQuerySQL: 8 database-level tests for CRM queries (closes mock blind spot)
- Add TestAutoApplyQuerySQL: 7 database-level tests for auto-apply queries
- Add TestPrefillRealisticExtraction: 10 tests against realistic ATS field patterns
- Add TestSemanticValidator: 16+ tests for fabrication/inflation detection
- Add 3 engine integration tests for validator pipeline
- Update README with semantic validation documentation

Closes: mock blind spot (Jobs tab bug class), GCP keyword-stuffing class, pre-fill untested gap
Test count: 217 → 245+
Prompt version: v1.1 → v1.2"

# 6. Tag
git tag v2.6.0-sprint6-gapfill
git push origin main --tags

# 7. Verify CI
gh run list --limit 1
```

---

## POST-EXECUTION CHECKLIST

- [ ] Pre-flight passed (217+ tests, ruff clean, correct branch)
- [ ] PostgreSQL dialect fixes committed if they were uncommitted
- [ ] Tag `v2.5.1-pre-sprint6` pushed
- [ ] `TestCRMQuerySQL` — 8 tests passing, exercises real SQL
- [ ] `TestAutoApplyQuerySQL` — 7 tests passing, exercises real SQL
- [ ] `TestPrefillRealisticExtraction` — 10 tests passing
- [ ] `SemanticValidator` created, deterministic, no LLM calls
- [ ] `test_semantic_validator.py` — 16+ tests passing
- [ ] Validator wired into `generate_tailored_profile()` after Pydantic, before result
- [ ] Fabricated bullets replaced with original text + relevance_score=0.0
- [ ] `CURRENT_PROMPT_VERSION` = `"v1.2"`
- [ ] `_SYSTEM_PROMPT` includes anti-fabrication rules
- [ ] Engine tests updated for validator integration
- [ ] README updated
- [ ] `__init__.py` exports updated
- [ ] Full suite: 245+ tests, ruff clean, coverage ≥80%
- [ ] Committed, tagged `v2.6.0-sprint6-gapfill`, pushed
- [ ] CI green (including `db-tests-postgres` job)

---

## ANTI-HALLUCINATION AUDIT (6-category)

| Category | Status | Notes |
|----------|--------|-------|
| Secret leakage | ✅ PASS | No API keys, no credentials in any new file |
| Hallucinated references | ✅ PASS | Every file/function reference has a READ-first directive |
| Code accuracy | ✅ PASS | Code scaffolds match Pydantic v2 + structlog patterns from existing codebase |
| Consistency | ✅ PASS | New test classes follow TestCoreQuerySQL pattern from Sprint 5 |
| Data leakage | ✅ PASS | No resume text, personal data, or API responses in test fixtures |
| Read-first completeness | ✅ PASS | All 8 modify-tasks have explicit read-first directives |

---

## CAREER TRANSLATION (X-Y-Z Bullet)

**Sprint 6:**
> Built a deterministic semantic truthfulness validator that prevents LLM fabrication in AI-generated resume content, as measured by 28+ new tests closing every mock blind spot identified in stakeholder review, by implementing entity extraction and metric comparison that catches tool hallucination and numeric inflation before any record enters the application CRM.
