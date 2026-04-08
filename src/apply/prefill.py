"""Pre-fill engine: maps resume data + tailored bullets to common ATS form fields."""
from __future__ import annotations

import re
from pathlib import Path

import structlog

from src.models.entities import ApplicationCreate, ApplicationFieldCreate, FieldSource, FieldType

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Common ATS field definitions
# ---------------------------------------------------------------------------

# Standard fields found on most job application forms.
# Each tuple: (field_name, field_type, source_strategy)
COMMON_ATS_FIELDS: list[tuple[str, FieldType, FieldSource]] = [
    ("full_name", FieldType.TEXT, FieldSource.RESUME),
    ("email", FieldType.EMAIL, FieldSource.RESUME),
    ("phone", FieldType.PHONE, FieldSource.RESUME),
    ("location", FieldType.TEXT, FieldSource.RESUME),
    ("linkedin_url", FieldType.URL, FieldSource.RESUME),
    ("portfolio_url", FieldType.URL, FieldSource.PROFILE),
    ("current_company", FieldType.TEXT, FieldSource.RESUME),
    ("current_title", FieldType.TEXT, FieldSource.RESUME),
    ("years_experience", FieldType.TEXT, FieldSource.RESUME),
    ("education", FieldType.TEXT, FieldSource.RESUME),
    ("work_authorization", FieldType.SELECT, FieldSource.PROFILE),
    ("requires_sponsorship", FieldType.CHECKBOX, FieldSource.PROFILE),
    ("desired_salary", FieldType.TEXT, FieldSource.PROFILE),
    ("start_date", FieldType.TEXT, FieldSource.PROFILE),
    ("resume_text", FieldType.TEXTAREA, FieldSource.RESUME),
    ("cover_letter", FieldType.TEXTAREA, FieldSource.AI_GENERATED),
]


class PreFillEngine:
    """
    Maps resume data to common ATS form fields with confidence scoring.

    Interview point: "The pre-fill engine uses a deterministic extraction
    pipeline for structured fields (name, email, phone) and reserves LLM
    calls only for unstructured content (cover letters). This keeps the
    system predictable and testable while using AI where it adds value."
    """

    def __init__(self, resume_path: str | None = None):
        self._resume_path = resume_path or str(Path("data") / "resume.txt")
        self._resume_text: str | None = None
        self._parsed_fields: dict[str, str] = {}

    def _load_resume(self) -> str:
        """Load and cache resume text."""
        if self._resume_text is None:
            with open(self._resume_path, encoding="utf-8") as f:
                self._resume_text = f.read()
            self._parse_resume_fields()
        return self._resume_text

    def _parse_resume_fields(self) -> None:
        """Extract structured fields from resume text using regex."""
        text = self._resume_text or ""

        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if lines:
            self._parsed_fields["full_name"] = lines[0]

        email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
        if email_match:
            self._parsed_fields["email"] = email_match.group()

        phone_match = re.search(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text)
        if phone_match:
            self._parsed_fields["phone"] = phone_match.group()

        linkedin_match = re.search(r"linkedin\.com/in/[\w-]+", text, re.IGNORECASE)
        if linkedin_match:
            self._parsed_fields["linkedin_url"] = "https://" + linkedin_match.group()

        location_match = re.search(r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)*,\s*[A-Z]{2})", text)
        if location_match:
            self._parsed_fields["location"] = location_match.group()

        exp_match = re.search(
            r"(?:EXPERIENCE|Experience).*?\n+(.+?)\s*[—–-]\s*(.+?)(?:\s*\(|\n)",
            text,
            re.DOTALL,
        )
        if exp_match:
            self._parsed_fields["current_company"] = exp_match.group(1).strip()
            self._parsed_fields["current_title"] = exp_match.group(2).strip()

        edu_match = re.search(r"(?:EDUCATION|Education).*?\n+(.+?)(?:\n\n|\Z)", text, re.DOTALL)
        if edu_match:
            self._parsed_fields["education"] = edu_match.group(1).strip().split("\n")[0].strip()

        years_match = re.search(r"(\d+)\+?\s*years", text, re.IGNORECASE)
        if years_match:
            self._parsed_fields["years_experience"] = years_match.group(1) + "+ years"

    def prefill_application(self, job_id: int, profile_id: int = 1) -> ApplicationCreate:
        """
        Generate a pre-filled application for a job listing.

        Returns an ApplicationCreate with all extractable fields populated
        and confidence scores reflecting extraction reliability.
        """
        self._load_resume()

        fields: list[ApplicationFieldCreate] = []
        total_confidence = 0.0
        field_count = 0

        for field_name, field_type, source in COMMON_ATS_FIELDS:
            value = self._parsed_fields.get(field_name)
            confidence: float | None = None

            if field_name == "resume_text":
                value = self._resume_text
                confidence = 1.0
            elif field_name == "cover_letter":
                value = None
                confidence = None
                source = FieldSource.AI_GENERATED
            elif field_name in ("work_authorization", "requires_sponsorship", "desired_salary", "start_date"):
                value = self._get_profile_default(field_name)
                confidence = 0.6
            elif value:
                confidence = 0.95 if field_name in ("email", "phone", "full_name") else 0.8
            else:
                confidence = 0.0
                value = None

            if confidence is not None:
                total_confidence += confidence
                field_count += 1

            fields.append(
                ApplicationFieldCreate(
                    field_name=field_name,
                    field_type=field_type,
                    field_value=value,
                    confidence=confidence,
                    source=source if value else None,
                )
            )

        avg_confidence = total_confidence / field_count if field_count > 0 else 0.0

        logger.info(
            "application_prefilled",
            job_id=job_id,
            fields_populated=sum(1 for field in fields if field.field_value),
            fields_total=len(fields),
            avg_confidence=round(avg_confidence, 2),
        )

        return ApplicationCreate(
            job_id=job_id,
            profile_id=profile_id,
            confidence_score=round(avg_confidence, 2),
            fields=fields,
            notes=f"Auto pre-filled {sum(1 for field in fields if field.field_value)}/{len(fields)} fields",
        )

    @staticmethod
    def _get_profile_default(field_name: str) -> str | None:
        """Return sensible defaults for profile-level fields."""
        defaults = {
            "work_authorization": "Authorized to work in the US",
            "requires_sponsorship": "No",
            "desired_salary": "",
            "start_date": "Immediately available",
        }
        return defaults.get(field_name)
