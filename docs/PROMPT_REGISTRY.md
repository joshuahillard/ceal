# Ceal Prompt Registry
**LLM prompt version tracking for A/B testing and drift detection**
*Created: April 3, 2026*

---

## Active Prompts

| Prompt ID | Component | Version | Model | Last Updated | Notes |
|-----------|-----------|---------|-------|-------------|-------|
| `RANKER_V1` | `src/ranker/llm_ranker.py` | 1.0 | Claude (httpx) | Sprint 2 | 0.0-1.0 match scoring |
| `TAILORING_V1` | `src/tailoring/engine.py` | 1.1 | Claude (httpx) | Sprint 2 | X-Y-Z bullet generation + fidelity guardrail |
| `REGIME_V1` | `src/ranker/regime_classifier.py` | 1.0 | Vertex AI | Sprint 9 | Tier 1/2/3 classification, fail-open |
| `COVERLETTER_V1` | `src/document/coverletter_engine.py` | 1.0 | Claude (httpx) | Sprint 10 | 5-paragraph cover letter arc |

## How to Update

When changing an LLM prompt:
1. Bump the version in the source file (`PROMPT_VERSION` or equivalent constant)
2. Update this registry with the new version and date
3. The version string is persisted alongside output for A/B analysis

## Retired Prompts

| Prompt ID | Component | Retired | Reason |
|-----------|-----------|---------|--------|
| *(none yet)* | | | |

---

*Maintained by: AI Architect persona*
