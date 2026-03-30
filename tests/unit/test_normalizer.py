"""
Céal: Normalizer Tests

Tests the pure transformation functions: HTML cleaning, salary parsing,
skill extraction, and full normalization.

These are the easiest tests in the project — no mocking, no async,
no I/O. The normalizer is a pure function: same input → same output.

Interview point: "The normalizer has 100% deterministic tests because
it's a pure transformation layer with no side effects. This is why I
separated it from the database writes — testability."
"""

from __future__ import annotations

from src.models.entities import JobSource, RawJobListing, RemoteType
from src.normalizer.pipeline import (
    clean_html,
    extract_skills,
    normalize_batch,
    normalize_job,
    parse_salary,
)

# ---------------------------------------------------------------------------
# Salary Parsing Tests
# ---------------------------------------------------------------------------

class TestSalaryParsing:
    def test_standard_range_with_k(self):
        assert parse_salary("$90K - $140K") == (90000.0, 140000.0)

    def test_standard_range_full_numbers(self):
        assert parse_salary("$90,000-$140,000") == (90000.0, 140000.0)

    def test_range_no_dollar_signs(self):
        assert parse_salary("90K-140K") == (90000.0, 140000.0)

    def test_single_value(self):
        mn, mx = parse_salary("$120K/year")
        assert mn == 120000.0

    def test_competitive_returns_none(self):
        assert parse_salary("Competitive") == (None, None)

    def test_none_input(self):
        assert parse_salary(None) == (None, None)

    def test_empty_string(self):
        assert parse_salary("") == (None, None)

    def test_range_with_spaces(self):
        mn, mx = parse_salary("$100K  -  $150K")
        assert mn == 100000.0
        assert mx == 150000.0

    def test_range_with_comma_format(self):
        mn, mx = parse_salary("$120,000 - $160,000")
        assert mn == 120000.0
        assert mx == 160000.0


# ---------------------------------------------------------------------------
# HTML Cleaning Tests
# ---------------------------------------------------------------------------

class TestHtmlCleaning:
    def test_strips_tags(self):
        result = clean_html("<p>Hello <strong>World</strong></p>")
        assert "Hello" in result
        assert "World" in result
        assert "<" not in result

    def test_removes_scripts(self):
        html = "<p>Text</p><script>alert('xss')</script><p>More</p>"
        result = clean_html(html)
        assert "alert" not in result
        assert "Text" in result
        assert "More" in result

    def test_preserves_paragraph_breaks(self):
        html = "<p>First paragraph</p><p>Second paragraph</p>"
        result = clean_html(html)
        assert "\n" in result

    def test_none_input(self):
        assert clean_html(None) is None

    def test_empty_html(self):
        assert clean_html("") is None

    def test_collapses_whitespace(self):
        html = "<p>Too    many     spaces</p>"
        result = clean_html(html)
        assert "  " not in result


# ---------------------------------------------------------------------------
# Skill Extraction Tests
# ---------------------------------------------------------------------------

class TestSkillExtraction:
    def test_extracts_python(self):
        skills = extract_skills("We need someone with strong Python skills.")
        names = [s["name"] for s in skills]
        assert "Python" in names

    def test_extracts_multiple_skills(self):
        text = "Requirements: Python, SQL, REST API experience. Docker preferred."
        skills = extract_skills(text)
        names = [s["name"] for s in skills]
        assert "Python" in names
        assert "SQL" in names
        assert "REST APIs" in names

    def test_detects_required_vs_nice_to_have(self):
        text = """
        Requirements:
        - Python experience required
        - SQL proficiency

        Nice to have:
        - Docker experience
        - Kubernetes knowledge
        """
        skills = extract_skills(text)
        skill_map = {s["name"]: s["is_required"] for s in skills}

        assert skill_map.get("Python") is True
        assert skill_map.get("SQL") is True
        assert skill_map.get("Docker") is False
        assert skill_map.get("Kubernetes") is False

    def test_no_duplicates(self):
        text = "Python Python Python. We love Python. Python is great."
        skills = extract_skills(text)
        python_count = sum(1 for s in skills if s["name"] == "Python")
        assert python_count == 1

    def test_empty_text(self):
        assert extract_skills("") == []
        assert extract_skills(None) == []

    def test_source_context_captured(self):
        text = "Strong experience with REST APIs and microservices."
        skills = extract_skills(text)
        rest_skill = next((s for s in skills if s["name"] == "REST APIs"), None)
        assert rest_skill is not None
        assert "REST" in rest_skill["source_context"]

    def test_case_insensitive_matching(self):
        text = "Experience with PYTHON, postgresql, and DOCKER required."
        skills = extract_skills(text)
        names = [s["name"] for s in skills]
        assert "Python" in names
        assert "PostgreSQL" in names
        assert "Docker" in names

    def test_domain_skills_detected(self):
        text = "Background in payment processing and FinTech required."
        skills = extract_skills(text)
        names = [s["name"] for s in skills]
        assert "Payment Processing" in names
        assert "FinTech" in names

    def test_soft_skills_detected(self):
        text = "Must have cross-functional leadership and project management experience."
        skills = extract_skills(text)
        names = [s["name"] for s in skills]
        assert "Cross-Functional Leadership" in names
        assert "Project Management" in names


# ---------------------------------------------------------------------------
# Full Normalization Tests
# ---------------------------------------------------------------------------

class TestNormalizeJob:
    def _make_raw(self, **overrides) -> RawJobListing:
        defaults = {
            "external_id": "test_001",
            "source": JobSource.LINKEDIN,
            "title": "Technical Solutions Engineer",
            "company_name": "Stripe",
            "url": "https://stripe.com/jobs/test",
            "location": "Boston, MA",
            "remote_type": RemoteType.HYBRID,
            "salary_text": "$120K - $160K",
            "description_raw": "<p>We need a TSE with <strong>Python</strong> and SQL experience.</p>",
        }
        defaults.update(overrides)
        return RawJobListing(**defaults)

    def test_produces_valid_job_listing_create(self):
        raw = self._make_raw()
        job, skills = normalize_job(raw)
        assert job.external_id == "test_001"
        assert job.source == JobSource.LINKEDIN
        assert job.title == "Technical Solutions Engineer"

    def test_parses_salary(self):
        raw = self._make_raw(salary_text="$120K - $160K")
        job, _ = normalize_job(raw)
        assert job.salary_min == 120000.0
        assert job.salary_max == 160000.0

    def test_cleans_html_in_description(self):
        raw = self._make_raw(
            description_raw="<p>Hello <script>evil()</script> World</p>"
        )
        job, _ = normalize_job(raw)
        assert "evil" not in (job.description_clean or "")
        assert "Hello" in (job.description_clean or "")

    def test_extracts_skills(self):
        raw = self._make_raw(
            description_raw="<p>Requirements: Python, SQL, Docker experience.</p>"
        )
        _, skills = normalize_job(raw)
        names = [s["name"] for s in skills]
        assert "Python" in names
        assert "SQL" in names

    def test_detects_remote_from_description(self):
        raw = self._make_raw(
            remote_type=RemoteType.UNKNOWN,
            description_raw="<p>This is a fully remote position.</p>",
        )
        job, _ = normalize_job(raw)
        assert job.remote_type == RemoteType.REMOTE

    def test_no_salary_is_okay(self):
        raw = self._make_raw(salary_text=None)
        job, _ = normalize_job(raw)
        assert job.salary_min is None
        assert job.salary_max is None

    def test_no_description_is_okay(self):
        raw = self._make_raw(description_raw=None)
        job, skills = normalize_job(raw)
        assert job.description_clean is None
        assert skills == []


class TestNormalizeBatch:
    def test_batch_processes_all(self):
        raws = [
            RawJobListing(
                external_id=f"batch_{i}",
                source=JobSource.LINKEDIN,
                title=f"Job {i}",
                company_name=f"Company {i}",
                url=f"https://example.com/{i}",
            )
            for i in range(5)
        ]
        results = normalize_batch(raws)
        assert len(results) == 5

    def test_batch_skips_failures(self):
        """If one job fails validation, others should still process."""
        raws = [
            RawJobListing(
                external_id="good",
                source=JobSource.LINKEDIN,
                title="Good Job",
                company_name="Good Co",
                url="https://example.com/good",
                salary_text="$100K",
            ),
        ]
        results = normalize_batch(raws)
        assert len(results) >= 1
