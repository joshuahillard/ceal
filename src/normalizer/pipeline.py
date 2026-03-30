"""
Céal: Normalizer Pipeline (Transform Stage)

Takes RawJobListing objects from the scraper and produces clean,
validated JobListingCreate records ready for the database.

This is the "T" in ETL — Extract (scraper), Transform (this), Load (database).

Responsibilities:
  1. Strip HTML tags from descriptions
  2. Parse salary text into numeric min/max fields
  3. Extract skills mentioned in the job description
  4. Detect remote type from description if not already set
  5. Validate everything through Pydantic before it touches the DB

Interview point: "The normalizer is a pure transformation stage — no I/O,
no side effects, fully deterministic. Given the same input, it always
produces the same output. This makes it trivially testable and easy to
reason about in a pipeline that otherwise has async I/O everywhere."
"""

from __future__ import annotations

import re

import structlog
from bs4 import BeautifulSoup

from src.models.entities import (
    JobListingCreate,
    RawJobListing,
    RemoteType,
)

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Salary Parsing
# ---------------------------------------------------------------------------
# Why a dedicated parser? Job boards encode salary in dozens of formats:
#   "$90K - $140K", "$90,000-$140,000/yr", "90k-140k", "$120K/year"
# The regex handles the most common patterns. Edge cases return None
# rather than bad data — the ranker can still work without salary info.

# Matches: $90K, $90,000, 90K, 90000, etc.
_SALARY_PATTERN = re.compile(
    r"\$?\s*(\d{2,3})[,.]?(\d{3})?\s*[kK]?\s*"
)

# Matches salary ranges: "$90K - $140K", "$90,000-$140,000"
_SALARY_RANGE_PATTERN = re.compile(
    r"\$?\s*(\d{2,3}),?(\d{3})?\s*[kK]?"
    r"\s*[-–—to]+\s*"
    r"\$?\s*(\d{2,3}),?(\d{3})?\s*[kK]?"
)


def parse_salary(text: str | None) -> tuple[float | None, float | None]:
    """
    Parse salary text into (min, max) floats.

    Returns (None, None) if unparseable — better to have no data
    than wrong data in a numeric field.

    Examples:
        "$90K - $140K"      → (90000.0, 140000.0)
        "$90,000-$140,000"  → (90000.0, 140000.0)
        "$120K/year"        → (120000.0, None)
        "Competitive"       → (None, None)
    """
    if not text:
        return None, None

    text = text.strip()

    # Try range first
    range_match = _SALARY_RANGE_PATTERN.search(text)
    if range_match:
        min_val = _parse_salary_number(range_match.group(1), range_match.group(2), text)
        max_val = _parse_salary_number(range_match.group(3), range_match.group(4), text)
        return min_val, max_val

    # Try single value
    single_match = _SALARY_PATTERN.search(text)
    if single_match:
        val = _parse_salary_number(single_match.group(1), single_match.group(2), text)
        return val, None

    return None, None


def _parse_salary_number(
    main_digits: str | None,
    trailing_digits: str | None,
    original_text: str,
) -> float | None:
    """Convert matched digits into a salary float."""
    if not main_digits:
        return None

    if trailing_digits:
        # Full number: "90,000" or "140,000"
        return float(main_digits + trailing_digits)

    # Short form: "90K" or "140K"
    num = float(main_digits)
    # If the number is small (< 1000), it's likely in K notation
    if num < 1000 and ("k" in original_text.lower()):
        return num * 1000
    # If < 1000 and no K, still likely thousands for salary context
    if num < 1000:
        return num * 1000

    return num


# ---------------------------------------------------------------------------
# HTML Cleaning
# ---------------------------------------------------------------------------

def clean_html(raw_html: str | None) -> str | None:
    """
    Strip HTML tags and normalize whitespace from job descriptions.

    Preserves paragraph breaks as double newlines for readability.
    """
    if not raw_html:
        return None

    soup = BeautifulSoup(raw_html, "lxml")

    # Remove script and style elements
    for element in soup(["script", "style"]):
        element.decompose()

    # Get text with newlines for block elements
    text = soup.get_text(separator="\n", strip=True)

    # Normalize whitespace: collapse multiple blank lines to one
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse multiple spaces to one
    text = re.sub(r"[ \t]+", " ", text)
    # Strip leading/trailing whitespace per line
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)

    return text.strip() if text.strip() else None


# ---------------------------------------------------------------------------
# Skill Extraction
# ---------------------------------------------------------------------------
# This is a keyword-based extractor for Phase 1. In Phase 2, we'll
# replace this with an LLM-based extractor that understands context
# (e.g., "Python" in "Monty Python fan" vs "Python 3.10 required").
#
# Interview point: "I started with keyword matching for speed and
# simplicity, with the architecture designed to swap in NLP-based
# extraction later. The skill extraction is behind a function interface,
# so the normalizer doesn't care how skills are found."

# Skills to look for, grouped by how they appear in job descriptions.
# Each tuple is (display_name, [patterns_to_match])
SKILL_PATTERNS: list[tuple[str, list[str]]] = [
    # Languages
    ("Python", [r"\bPython\b"]),
    ("SQL", [r"\bSQL\b"]),
    ("JavaScript", [r"\bJavaScript\b", r"\bJS\b"]),
    ("TypeScript", [r"\bTypeScript\b", r"\bTS\b"]),
    ("Go", [r"\bGolang\b", r"\bGo\s+(?:lang|programming)\b"]),
    ("Bash", [r"\bBash\b", r"\bshell\s+script"]),
    # Frameworks
    ("FastAPI", [r"\bFastAPI\b"]),
    ("Flask", [r"\bFlask\b"]),
    ("Django", [r"\bDjango\b"]),
    ("React", [r"\bReact(?:\.js|JS)?\b"]),
    ("asyncio", [r"\basyncio\b", r"\basync\s*/\s*await\b", r"\basynchronous\s+programming\b"]),
    # Infrastructure
    ("Docker", [r"\bDocker\b", r"\bcontainer(?:s|ization)?\b"]),
    ("Kubernetes", [r"\bKubernetes\b", r"\bK8s\b"]),
    ("Linux", [r"\bLinux\b", r"\bUbuntu\b", r"\bCentOS\b"]),
    ("CI/CD", [r"\bCI\s*/\s*CD\b", r"\bcontinuous\s+(?:integration|deployment|delivery)\b"]),
    ("GitHub Actions", [r"\bGitHub\s+Actions\b"]),
    ("Terraform", [r"\bTerraform\b", r"\bIaC\b"]),
    # Cloud
    ("AWS", [r"\bAWS\b", r"\bAmazon\s+Web\s+Services\b"]),
    ("GCP", [r"\bGCP\b", r"\bGoogle\s+Cloud\b"]),
    ("Azure", [r"\bAzure\b"]),
    # Databases
    ("PostgreSQL", [r"\bPostgreSQL\b", r"\bPostgres\b"]),
    ("Redis", [r"\bRedis\b"]),
    ("MongoDB", [r"\bMongoDB\b", r"\bMongo\b"]),
    # Methodologies
    ("REST APIs", [r"\bREST\s*(?:ful)?\s*API", r"\bAPI\s+(?:design|development|integration)"]),
    ("GraphQL", [r"\bGraphQL\b"]),
    ("Event-Driven Architecture", [r"\bevent[- ]driven\b", r"\bmessage\s+queue", r"\bpub\s*/\s*sub\b"]),
    ("Agile", [r"\bAgile\b", r"\bScrum\b", r"\bSprint\b"]),
    # Domain
    ("Payment Processing", [r"\bpayment(?:s)?\s+(?:processing|infrastructure|system)", r"\bPCI\b"]),
    ("FinTech", [r"\bFinTech\b", r"\bfinancial\s+technology\b"]),
    # Soft Skills (relevant for TSE/TPM roles)
    ("Technical Escalation Management", [r"\btechnical\s+escalation", r"\bescalation\s+management"]),
    ("Cross-Functional Leadership", [r"\bcross[- ]functional\b", r"\bcross[- ]team\b"]),
    ("Customer-Facing Communication", [r"\bcustomer[- ]facing\b", r"\bclient[- ]facing\b"]),
    ("Project Management", [r"\bproject\s+manag", r"\bTPM\b", r"\bprogram\s+manag"]),
    # Tools
    ("JIRA", [r"\bJIRA\b", r"\bJira\b"]),
    ("Salesforce", [r"\bSalesforce\b"]),
    ("Git", [r"\bGit(?:Hub|Lab)?\b"]),
]

# Pre-compile patterns for performance
_COMPILED_SKILLS: list[tuple[str, list[re.Pattern]]] = [
    (name, [re.compile(p, re.IGNORECASE) for p in patterns])
    for name, patterns in SKILL_PATTERNS
]


def extract_skills(text: str | None) -> list[dict]:
    """
    Extract mentioned skills from job description text.

    Returns a list of dicts with:
      - name: skill display name
      - is_required: True if in a "required" section, False if "nice to have"
      - source_context: the sentence where the skill was mentioned

    Interview point: "Skill extraction feeds the matching algorithm.
    I distinguish 'required' from 'nice-to-have' because that changes
    the match score calculation — a missing required skill is weighted
    more heavily than a missing nice-to-have."
    """
    if not text:
        return []

    found: list[dict] = []
    seen: set[str] = set()

    # Split into sections to detect required vs nice-to-have
    text.lower()
    is_nice_to_have_section = False

    # Process line by line to track section context
    lines = text.split("\n")
    for line in lines:
        line_lower = line.lower().strip()

        # Detect section headers
        if any(phrase in line_lower for phrase in [
            "nice to have", "preferred", "bonus", "plus",
            "ideal candidate", "would be great",
        ]):
            is_nice_to_have_section = True
        elif any(phrase in line_lower for phrase in [
            "required", "requirement", "must have", "qualifications",
            "what you'll", "what we're looking", "responsibilities",
            "about the role", "you will", "you'll",
        ]):
            is_nice_to_have_section = False

        # Search for skills in this line
        for skill_name, patterns in _COMPILED_SKILLS:
            if skill_name in seen:
                continue

            for pattern in patterns:
                if pattern.search(line):
                    seen.add(skill_name)
                    found.append({
                        "name": skill_name,
                        "is_required": not is_nice_to_have_section,
                        "source_context": line.strip()[:200],
                    })
                    break

    return found


# ---------------------------------------------------------------------------
# Normalizer — the main transformation function
# ---------------------------------------------------------------------------

def normalize_job(raw: RawJobListing) -> tuple[JobListingCreate, list[dict]]:
    """
    Transform a RawJobListing into a clean JobListingCreate + extracted skills.

    This is a pure function — no I/O, no side effects.
    Returns (validated_job, extracted_skills).

    The caller (the pipeline orchestrator) handles:
      1. Inserting the job into the database
      2. Linking the extracted skills via the job_skills table
    """
    # Clean the description HTML
    description_clean = clean_html(raw.description_raw)

    # Parse salary from text
    salary_min, salary_max = parse_salary(raw.salary_text)

    # Detect remote type from description if not already set
    remote_type = raw.remote_type
    if remote_type == RemoteType.UNKNOWN and description_clean:
        remote_type = _detect_remote_from_description(description_clean)

    # Extract skills from the clean description
    skills = extract_skills(description_clean)

    # Build the validated JobListingCreate
    job = JobListingCreate(
        external_id=raw.external_id,
        source=raw.source,
        title=raw.title,
        company_name=raw.company_name,
        url=raw.url,
        location=raw.location,
        remote_type=remote_type,
        salary_min=salary_min,
        salary_max=salary_max,
        description_raw=raw.description_raw,
        description_clean=description_clean,
    )

    logger.debug(
        "job_normalized",
        external_id=raw.external_id,
        skills_found=len(skills),
        has_salary=salary_min is not None,
    )

    return job, skills


def normalize_batch(
    raw_jobs: list[RawJobListing],
) -> list[tuple[JobListingCreate, list[dict]]]:
    """
    Normalize a batch of raw jobs. Skips jobs that fail validation
    rather than crashing the entire batch.
    """
    results: list[tuple[JobListingCreate, list[dict]]] = []

    for raw in raw_jobs:
        try:
            results.append(normalize_job(raw))
        except Exception as exc:
            logger.warning(
                "normalize_failed",
                external_id=raw.external_id,
                error=str(exc),
            )

    logger.info(
        "batch_normalized",
        input_count=len(raw_jobs),
        output_count=len(results),
        dropped=len(raw_jobs) - len(results),
    )

    return results


def _detect_remote_from_description(text: str) -> RemoteType:
    """Fallback remote type detection from description text."""
    text_lower = text.lower()
    if "fully remote" in text_lower or "100% remote" in text_lower:
        return RemoteType.REMOTE
    if "hybrid" in text_lower:
        return RemoteType.HYBRID
    if "on-site" in text_lower or "in-office" in text_lower:
        return RemoteType.ONSITE
    return RemoteType.UNKNOWN
