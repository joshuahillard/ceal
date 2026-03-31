"""
Céal Phase 2: Resume Parser Stub Tests

Validates that the ResumeProfileParser stub raises NotImplementedError
until Wednesday's implementation session. This test will be replaced
with real parsing tests on 4/1.

TDD discipline: the test exists before the code. When we implement
the parser, this test becomes the migration gate — it must be updated
to test real behavior before the PR can merge.

Persona: [QA Lead] — stub coverage, contract verification
"""

import pytest

from src.tailoring.resume_parser import ResumeProfileParser


class TestResumeProfileParser:
    """Validates parser stub behavior and interface contract."""

    def test_parser_raises_not_implemented(self):
        """
        The parser stub must raise NotImplementedError.
        This is a gate: when we implement parsing (Wed 4/1),
        this test gets replaced with real validation tests.
        """
        parser = ResumeProfileParser()
        with pytest.raises(NotImplementedError):
            parser.parse(profile_id=1, raw_text="Full resume text...")

    def test_parser_accepts_correct_signature(self):
        """
        Verify the parser interface accepts profile_id (int) and
        raw_text (str). When implementation lands, this confirms
        the interface didn't drift.
        """
        parser = ResumeProfileParser()
        # The signature is correct if this reaches NotImplementedError
        # (not TypeError for wrong args)
        with pytest.raises(NotImplementedError):
            parser.parse(profile_id=42, raw_text="Josh Hillard\nBoston, MA\n...")

    def test_parser_instantiation(self):
        """Parser can be instantiated with no arguments."""
        parser = ResumeProfileParser()
        assert parser is not None
