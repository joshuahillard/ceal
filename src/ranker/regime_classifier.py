"""
Céal: Vertex AI Regime Classifier

Classifies job listings into tier strategy 1, 2, or 3 using Google
Vertex AI (Gemini). This is an OPTIONAL, fail-open module — if Vertex
AI is not configured or the API call fails, the pipeline continues
with zero degradation.

The classifier does NOT replace Claude. Claude still performs semantic
ranking (llm_ranker.py) and resume tailoring (engine.py). This module
adds a Google-native classifier for prompt strategy A/B experimentation.

Architecture:
    - Config from env: VERTEX_PROJECT_ID, VERTEX_LOCATION, VERTEX_MODEL
    - If VERTEX_PROJECT_ID is not set → returns None (fail-open)
    - If google-cloud-aiplatform is not installed → returns None
    - If API call fails or response is unparseable → returns None
    - On success → returns a validated RegimeClassification

Interview talking point:
    "The Vertex AI classifier is entirely optional and fail-open.
    If credentials are missing, the SDK isn't installed, or the API
    errors, it returns None and the pipeline proceeds unchanged.
    This lets me experiment with Google-native classification for
    A/B testing tier strategies without risking the production path."
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import structlog

from src.ranker.regime_models import RegimeClassification

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Classification Prompt
# ---------------------------------------------------------------------------

REGIME_PROMPT_TEMPLATE = """You are classifying a job listing into one of three strategy tiers.

## Tier Definitions
- **Tier 1 (Apply Now):** Companies where the candidate has direct domain overlap and should apply immediately. Examples: Stripe, Square, Plaid, Coinbase, Datadog, Toast — FinTech, payments, SaaS observability.
- **Tier 2 (Build Credential):** Companies that require additional cloud/infrastructure credentials before applying. Examples: Google Cloud, AWS, MongoDB, Cloudflare — need GCP/AWS certs or deeper infra experience.
- **Tier 3 (Campaign):** Aspirational roles at large companies requiring a long-term positioning campaign. Examples: Google L5 TPM, Amazon, Microsoft — need strategic networking and portfolio building.

## Candidate Profile
Technical Solutions Engineer / Technical Program Manager with 6+ years at Toast (FinTech/POS). Strong in Python, SQL, REST APIs, Linux, Docker, GCP, payment processing, technical escalation management, cross-functional leadership.

## Job Listing
**Title:** {job_title}
**Company:** {company_name}
**Location:** {location}
**Description:**
{description}

## Instructions
Classify this job into Tier 1, 2, or 3 based on:
1. Domain overlap with candidate's FinTech/payments/SaaS experience
2. Technical skill alignment (Python, SQL, APIs, cloud, infrastructure)
3. Seniority fit and required credential level
4. Application readiness vs. credential-building vs. long-term campaign

Respond with ONLY valid JSON:
{{
  "recommended_tier": <1, 2, or 3>,
  "confidence": <float 0.0-1.0>,
  "reasoning": "<2-3 sentence explanation>"
}}"""


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

async def classify_regime(
    job_id: int,
    job_title: str,
    company_name: str,
    location: str | None = None,
    description: str | None = None,
) -> RegimeClassification | None:
    """
    Classify a job listing into tier 1, 2, or 3 using Vertex AI.

    Returns None (fail-open) if:
        - VERTEX_PROJECT_ID is not set
        - google-cloud-aiplatform is not installed
        - API call fails
        - Response cannot be parsed into a valid classification
    """
    # Check config
    project_id = os.getenv("VERTEX_PROJECT_ID")
    if not project_id:
        logger.debug("regime_classifier_skipped", reason="VERTEX_PROJECT_ID not set")
        return None

    vertex_location = os.getenv("VERTEX_LOCATION", "us-east1")
    vertex_model = os.getenv("VERTEX_MODEL", "gemini-2.0-flash")

    # Check SDK availability
    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel
    except ImportError:
        logger.warning("regime_classifier_skipped", reason="google-cloud-aiplatform not installed")
        return None

    try:
        # Initialize Vertex AI
        vertexai.init(project=project_id, location=vertex_location)

        # Build prompt
        prompt = REGIME_PROMPT_TEMPLATE.format(
            job_title=job_title,
            company_name=company_name,
            location=location or "Not specified",
            description=(description or "No description available")[:4000],
        )

        # Call Vertex AI
        model = GenerativeModel(vertex_model)
        response = model.generate_content(prompt)
        raw_text = response.text

        # Parse response
        classification = _parse_response(raw_text, job_id, vertex_model)
        if classification:
            logger.info(
                "regime_classified",
                job_id=job_id,
                tier=classification.recommended_tier,
                confidence=classification.confidence,
            )
        return classification

    except Exception as exc:
        logger.warning(
            "regime_classifier_failed",
            job_id=job_id,
            error=str(exc),
        )
        return None


def _parse_response(
    raw: str,
    job_id: int,
    model_name: str,
) -> RegimeClassification | None:
    """
    Parse Vertex AI response JSON into a validated RegimeClassification.

    Returns None if response is unparseable or invalid.
    Strips markdown code fences (same pattern as engine.py).
    """
    try:
        cleaned = raw.strip()
        # Strip markdown code fences if present
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [line for line in lines if not line.strip().startswith("```")]
            cleaned = "\n".join(lines)

        parsed = json.loads(cleaned)

        now_iso = datetime.now(timezone.utc).isoformat()

        return RegimeClassification(
            job_id=job_id,
            recommended_tier=parsed["recommended_tier"],
            confidence=parsed["confidence"],
            reasoning=parsed["reasoning"],
            model_version=f"vertex-ai/{model_name}/{now_iso[:10]}",
        )

    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.warning(
            "regime_parse_failed",
            job_id=job_id,
            error=str(exc),
            raw_response=raw[:300],
        )
        return None
