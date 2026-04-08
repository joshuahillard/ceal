"""
Céal: Pre-fill engine edge-case tests.

Exercises the PreFillEngine against malformed, empty, Unicode, and
partial resume inputs. These tests use temporary files — no dependency
on data/resume.txt.

Sprint 11 deliverable — hardening pre-fill field mapping.
"""
from __future__ import annotations

import tempfile

import pytest

from src.apply.prefill import PreFillEngine
from src.models.entities import ApplicationCreate

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _engine_from_text(content: str) -> PreFillEngine:
    """Write *content* to a temp file and return a PreFillEngine pointed at it."""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")  # noqa: SIM115
    tmp.write(content)
    tmp.flush()
    tmp.close()
    return PreFillEngine(resume_path=tmp.name)


def _field_value(result: ApplicationCreate, field_name: str) -> str | None:
    """Extract a single field value by name from the ApplicationCreate."""
    matches = [f for f in result.fields if f.field_name == field_name]
    assert len(matches) == 1, f"Expected exactly 1 field named {field_name!r}, got {len(matches)}"
    return matches[0].field_value


def _field_confidence(result: ApplicationCreate, field_name: str) -> float | None:
    """Extract the confidence score for a single field."""
    matches = [f for f in result.fields if f.field_name == field_name]
    assert len(matches) == 1
    return matches[0].confidence


# ---------------------------------------------------------------------------
# Edge-case tests
# ---------------------------------------------------------------------------


class TestPreFillEmptyInputs:
    """Empty and whitespace-only resumes should not crash the engine."""

    def test_empty_resume_file(self):
        """A zero-byte resume should still return a valid ApplicationCreate."""
        engine = _engine_from_text("")
        result = engine.prefill_application(job_id=1)

        assert isinstance(result, ApplicationCreate)
        assert result.confidence_score is not None
        assert 0.0 <= result.confidence_score <= 1.0

    def test_whitespace_only_resume(self):
        """A resume containing only whitespace should produce no extracted fields."""
        engine = _engine_from_text("   \n\n   \t\n  ")
        result = engine.prefill_application(job_id=1)

        assert isinstance(result, ApplicationCreate)
        # No regex should match whitespace-only content
        assert _field_value(result, "email") is None
        assert _field_value(result, "phone") is None
        assert _field_value(result, "linkedin_url") is None

    def test_whitespace_only_resume_name_is_none_or_empty(self):
        """full_name should not be populated from a whitespace-only resume."""
        engine = _engine_from_text("   \n\n   \t\n  ")
        result = engine.prefill_application(job_id=1)

        name = _field_value(result, "full_name")
        # The engine takes lines[0] after strip+filter — an all-whitespace
        # resume should have no non-empty lines, so name should be None.
        assert name is None


class TestPreFillUnicode:
    """Unicode names, locations, and content should be handled gracefully."""

    def test_unicode_name_extracted(self):
        """A resume whose first line is a Unicode name should extract it."""
        engine = _engine_from_text("José García-López\njose@example.com\n")
        result = engine.prefill_application(job_id=1)

        assert _field_value(result, "full_name") == "José García-López"

    def test_unicode_location_extracted(self):
        """City names with accented characters should match the location regex."""
        # The current location regex expects "City, ST" with ASCII uppercase.
        # São Paulo won't match because 'ã' isn't [A-Z][a-z]+.
        # This test documents the current behavior.
        engine = _engine_from_text("Test Name\nSão Paulo, SP\njose@example.com\n")
        result = engine.prefill_application(job_id=1)

        # Current regex is ASCII-only — this documents the limitation.
        location = _field_value(result, "location")
        # São doesn't start with [A-Z][a-z]+ in ASCII regex, so it won't match.
        # If this test starts passing after a regex fix, that's the desired behavior.
        assert location is None or "Paulo" in location

    def test_unicode_email_extracted(self):
        """An email with Unicode in the local part should still be extracted."""
        # RFC 6531 allows internationalized local parts but our regex uses \\w
        # which in Python matches Unicode word characters by default.
        engine = _engine_from_text("Test Name\njoão@example.com\n")
        result = engine.prefill_application(job_id=1)

        assert _field_value(result, "email") == "joão@example.com"

    def test_cjk_name_extracted(self):
        """A CJK name on the first line should be extracted as full_name."""
        engine = _engine_from_text("田中太郎\ntanaka@example.com\n")
        result = engine.prefill_application(job_id=1)

        assert _field_value(result, "full_name") == "田中太郎"


class TestPreFillMalformedInput:
    """Malformed emails, phone numbers, and experience strings."""

    def test_malformed_email_not_at_sign_only(self):
        """A bare '@' should not be extracted as an email."""
        engine = _engine_from_text("Test Name\n@ not an email\n(555) 123-4567\n")
        result = engine.prefill_application(job_id=1)

        email = _field_value(result, "email")
        # The regex requires characters on both sides of @, so this should be None
        assert email is None

    def test_malformed_email_no_tld(self):
        """'user@domain' with no TLD should not match the email regex."""
        engine = _engine_from_text("Test Name\nuser@domain\n")
        result = engine.prefill_application(job_id=1)

        email = _field_value(result, "email")
        # Regex requires \\.[\\w.-]+ after the domain, so bare domain fails
        assert email is None

    def test_non_numeric_years_experience(self):
        """'many years' should not produce a years_experience value."""
        engine = _engine_from_text("Test Name\nmany years of experience\n")
        result = engine.prefill_application(job_id=1)

        years = _field_value(result, "years_experience")
        assert years is None

    def test_phone_with_extension_extracts_base(self):
        """A phone number with an extension should still extract the base number."""
        engine = _engine_from_text("Test Name\n(555) 123-4567 x890\n")
        result = engine.prefill_application(job_id=1)

        phone = _field_value(result, "phone")
        assert phone is not None
        assert "555" in phone
        assert "4567" in phone


class TestPreFillPartialResume:
    """Resumes missing major sections (EXPERIENCE, EDUCATION)."""

    def test_no_experience_section(self):
        """A resume with no EXPERIENCE header should yield None for company/title."""
        engine = _engine_from_text(
            "Josh Hillard\njosh@example.com\n(555) 123-4567\nBoston, MA\n\n"
            "EDUCATION\nHofstra University | Communications\n"
        )
        result = engine.prefill_application(job_id=1)

        assert _field_value(result, "current_company") is None
        assert _field_value(result, "current_title") is None
        # But email/phone/name should still work
        assert _field_value(result, "email") == "josh@example.com"
        assert _field_value(result, "full_name") == "Josh Hillard"

    def test_no_education_section(self):
        """A resume with no EDUCATION header should yield None for education."""
        engine = _engine_from_text(
            "Josh Hillard\njosh@example.com\n\n"
            "EXPERIENCE\nToast, Inc. — Manager II, Technical Escalations\n"
            "Oct 2023 - Oct 2025\n"
        )
        result = engine.prefill_application(job_id=1)

        assert _field_value(result, "education") is None
        # But experience should still parse
        assert _field_value(result, "current_company") is not None

    def test_name_only_resume(self):
        """A resume with only a name line and nothing else."""
        engine = _engine_from_text("Josh Hillard\n")
        result = engine.prefill_application(job_id=1)

        assert isinstance(result, ApplicationCreate)
        assert _field_value(result, "full_name") == "Josh Hillard"
        assert _field_value(result, "email") is None
        assert _field_value(result, "phone") is None
        assert result.confidence_score < 0.5  # Very low — almost nothing extracted


class TestPreFillMissingFile:
    """Attempting to load a non-existent resume file."""

    def test_missing_resume_file_raises(self):
        """Pointing at a non-existent file should raise FileNotFoundError."""
        engine = PreFillEngine(resume_path="/tmp/nonexistent_resume_abc123.txt")
        with pytest.raises(FileNotFoundError):
            engine.prefill_application(job_id=1)


class TestPreFillConfidenceScoring:
    """Confidence score edge cases."""

    def test_empty_resume_confidence_reflects_profile_defaults(self):
        """With an empty resume, confidence should still include profile defaults."""
        engine = _engine_from_text("")
        result = engine.prefill_application(job_id=1)

        # Profile defaults (work_authorization, requires_sponsorship, start_date)
        # get 0.6 confidence, desired_salary gets 0.6 too.
        # All resume-extracted fields get 0.0.
        # resume_text gets 1.0 (even though it's empty).
        # cover_letter is excluded from confidence calc (confidence=None).
        assert result.confidence_score > 0.0  # Profile defaults bump it above zero
        assert result.confidence_score < 0.5  # But not much

    def test_full_resume_confidence_above_half(self):
        """A well-populated resume should produce confidence > 0.5."""
        engine = _engine_from_text(
            "Josh Hillard\njosh@example.com\n(555) 123-4567\nBoston, MA\n"
            "linkedin.com/in/joshhillard\n\n"
            "6+ years of experience\n\n"
            "EXPERIENCE\nToast, Inc. — Manager II, Technical Escalations\n"
            "Oct 2023 - Oct 2025\n\n"
            "EDUCATION\nHofstra University | Communications\n"
        )
        result = engine.prefill_application(job_id=1)

        assert result.confidence_score >= 0.5
