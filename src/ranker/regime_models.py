"""
Céal: Regime Classification Models

Pydantic contracts for Vertex AI regime classification output.
The classifier recommends which existing tier strategy (1, 2, or 3)
best fits a job listing. These are the SAME tiers used throughout
the pipeline — no new taxonomy is introduced here.

Tier semantics (from company_tiers table):
    1 = Apply Now (Stripe, Square, Plaid, Coinbase, Datadog)
    2 = Build Credential (Google, AWS, MongoDB, Cloudflare)
    3 = Campaign (Google L5 TPM III, Customer Engineer II)

Interview talking point:
    "The regime classifier adds a Google-native ML signal for
    prompt A/B testing. It recommends a tier strategy for each
    job listing, stored separately from the company_tier lookup
    so we can compare the two signals. The existing Claude ranker
    and tailoring engine remain unchanged."
"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class RegimeClassification(BaseModel):
    """Vertex AI regime classification result for a single job listing."""

    job_id: int
    recommended_tier: int = Field(..., ge=1, le=3)
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str = Field(..., min_length=1)
    model_version: str = Field(..., min_length=1)

    @field_validator("recommended_tier")
    @classmethod
    def tier_must_be_valid(cls, v: int) -> int:
        if v not in (1, 2, 3):
            raise ValueError(f"Tier must be 1, 2, or 3, got {v}")
        return v


class RegimeStats(BaseModel):
    """Summary counts for dashboard display."""

    tier_1_count: int = 0
    tier_2_count: int = 0
    tier_3_count: int = 0
    unclassified_count: int = 0
    total_classified: int = 0
