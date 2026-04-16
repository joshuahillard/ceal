# Human-in-the-Loop Governance — Ceal

*Binding contract between Ceal's automation and Josh Hillard's final authority over career-critical decisions.*

---

## Why Governance Matters Here

Ceal automates steps in a career pipeline where mistakes have real consequences: a hallucinated metric on a resume damages credibility, a misranked listing wastes a limited application slot, and a submitted application cannot be unsent. The governance contract defines what the system may do autonomously and where human authority is non-negotiable.

---

## Governance Invariants

1. **Ceal may discover, score, and rank job listings autonomously.** The pipeline runs end-to-end without human intervention for scraping, normalizing, and ranking.

2. **Ceal may rewrite resume bullets subject to the Semantic Fidelity Guardrail.** The guardrail (v1.1) is the automated check. Bullets that pass the guardrail are eligible for use — but the guardrail itself may not be weakened without human decision.

3. **Ceal may generate cover letter drafts.** These are proposals, not commitments. Generated content is presented for review, not auto-submitted.

4. **Ceal may pre-fill application form fields.** The ATS prefill engine produces deterministic field mappings. Low-confidence fields are flagged.

5. **Ceal may NOT submit applications without human approval.** The approval queue is a hard gate. No path through the code bypasses it.

6. **Ceal may NOT fabricate resume metrics.** The Semantic Fidelity Guardrail rejects hallucinated numbers. This is a core-fails-closed invariant — not enrichment.

---

## Authority Boundary

### Automation Is Allowed To:
- Scrape job listings from LinkedIn guest API
- Parse, normalize, and deduplicate listings
- Score listings via Claude API (0.0–1.0)
- Classify listings via Vertex AI (fail-open enrichment)
- Rewrite resume bullets using Claude API (subject to guardrail)
- Generate cover letter content via Claude API
- Pre-fill ATS form fields deterministically
- Queue applications for human review
- Track application state machine transitions
- Generate PDF documents on demand

### Automation Is NOT Allowed To:
- Submit any application without explicit human approval
- Override the Semantic Fidelity Guardrail
- Introduce metrics, percentages, or dollar figures not present in the original resume
- Modify the tier strategy (Tier 1/2/3 company classification) without human decision
- Delete or archive applications without human action
- Change database schemas without dual-file updates (schema.sql + schema_postgres.sql)

### Human Authority (Josh) Decides:
- Which applications to approve for submission
- Whether cover letter content accurately represents experience
- Tier strategy adjustments (which companies to target at each tier)
- Resume content accuracy (the source of truth is Josh's actual experience)
- Feature prioritization and sprint scope
- Go/no-go on any career-critical submission

---

## Decision Contracts

### Ranking Decision
- **Approve (high score):** Listing appears prominently in the jobs view. Eligible for tailoring and application.
- **Low score:** Listing appears lower in ranking. Not filtered out — human can still choose to apply.
- **Parse failure:** Listing is not ranked. Logged as error. Does not appear in scored results.

### Tailoring Decision
- **Guardrail pass:** Tailored bullet is stored and presented alongside the original.
- **Guardrail reject:** Original bullet preserved. Tailored version discarded. Rejection logged.
- **No original bullet:** Section is skipped. No fabrication.

### Application Decision
- **Queued:** Pre-filled form enters approval queue with confidence scores per field.
- **Human approved:** Application moves to APPLIED state. Fields are finalized.
- **Human rejected:** Application stays in queue or is archived. Not submitted.

### Cover Letter Decision
- **Generated:** Content produced by Claude API, rendered as PDF via ReportLab.
- **Human reviews:** PDF is downloaded, reviewed, and submitted manually.
- **No auto-send:** Cover letters are never transmitted without human action.

---

## Application State Machine

```
PROSPECT → APPLIED → INTERVIEWING → OFFER
    ↓          ↓           ↓           ↓
 ARCHIVED   REJECTED   REJECTED    REJECTED
```

**State transitions require explicit action.** No automatic promotion from PROSPECT to APPLIED — the approval queue enforces human review.

**Stale reminders:** Applications in APPLIED state without activity trigger follow-up reminders. Reminders are informational, not automated actions.

---

## Semantic Fidelity Guardrail v1.1

The guardrail is the primary automated governance mechanism for resume content integrity:

- Detects metrics (percentages, dollar figures, quantities) in tailored bullets that are absent from the original
- Detects semantic drift where the tailored bullet changes the meaning of the original
- Detects hallucinated job titles, tools, or outcomes
- Operates per-bullet (one rejection doesn't invalidate the batch)
- Fail-closed: rejected bullets are discarded, original preserved

**This guardrail may not be bypassed, weakened, or disabled without explicit human decision.** It is a governance control, not a convenience feature.

---

## Related Files

- `src/tailoring/engine.py` — Semantic Fidelity Guardrail v1.1 implementation
- `src/apply/prefill.py` — Deterministic ATS prefill (no LLM)
- `src/web/routes/apply.py` — Approval queue and review screen
- `src/web/routes/applications.py` — CRM state machine
- `docs/ai-onboarding/PROJECT_CONTEXT.md` — Full architecture reference
- `docs/ai-onboarding/RULES.md` — Engineering rules and conventions
