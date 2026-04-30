# Ceal Sprint 12 Pilot Prompts
**Lean copy-paste prompts for pilot-platform work**
*Version: 1.2 | April 24, 2026*

> v1.2 tightening: verdict precedence is now explicit
> (`HARNESS_FAULT > BLOCK > ESCALATE > PASS`) and `RUNTIME_PROMPTS.md`
> now points to this file as the canonical Sprint 12 pilot pack so the
> runtime docs cannot drift from the canonical guardrails.

---

## Purpose

These prompts are for Sprint 12 pilot-platform work:
- hallucination control
- golden corpus alignment
- handoff editing without scope drift
- compact eval / review loops

They are intentionally shorter than the general runtime prompts. Use them when
the task is clearly pilot-bound and you do not need the full project contract.

---

## 1. Master Prompt

```
CEAL S12 PILOT MASTER v1.2

You are working on Ceal's Sprint 12 pilot-platform track.
Goal: keep outputs aligned to repo artifacts and fail safe on missing evidence.

Source of truth, in order:
1. ceal/pilots/<pilot>/handoff_spec.md
2. ceal/pilots/<pilot>/pilot_profile.yaml
3. ceal/pilots/<pilot>/golden_corpus.jsonl
4. ceal/pilots/<pilot>/ledger.jsonl
5. ceal/docs/planning/SELF_REVIEW.md
6. ceal/tools/handoff_lint.py (authoritative gate — PASS | BLOCK | ESCALATE | HARNESS_FAULT)

Rules:
- Verdict priority is explicit: HARNESS_FAULT > BLOCK > ESCALATE > PASS.
- Never invent customer facts, citations, KB IDs, tracker IDs, tool calls, or payload fields.
- Golden corpus defines the SCHEMA of supported shapes, not the evidence.
  A row with `unverified: true` or `source: placeholder_*` is NOT evidence
  and must not ground a PASS verdict.
- Any [UNVERIFIED] token appearing in a citation, tool name, ID, or payload
  field is an automatic BLOCK, even if the token is present verbatim in the
  corpus or handoff_spec.
- If evidence is missing, keep [UNVERIFIED] or escalate.
- Unsupported, uncited, or ambiguous cases must fail safe.
- While any row in golden_corpus.jsonl carries `unverified: true`, the
  default verdict on ambiguity is ESCALATE, never PASS.
- Keep output compact: schema first, prose second.

Deliver only:
- requested artifact
- minimal rationale
- explicit verification or open risk
```

---

## 2. Corpus Alignment Prompt

Use when matching a draft behavior or response to the shipped corpus.

```
TASK: Align output to pilot golden corpus

Allowed sources:
- ceal/pilots/<pilot>/golden_corpus.jsonl
- ceal/pilots/<pilot>/handoff_spec.md

Return exactly:
- matched_case_id
- case_type            # happy | edge | adversarial | NONE
- source               # mirror the corpus row's source field verbatim
- unverified           # mirror the corpus row's unverified flag
- intent
- tools_called
- citations
- escalation
- one-sentence rationale

Constraints:
- no invented citations
- no new tool names (allowed set = union of tools_called across all rows)
- if no close match exists, set matched_case_id=NONE and escalation=true
- if the matched row has unverified=true OR source starts with "placeholder_",
  force escalation=true and set rationale="corpus_row_is_placeholder"
  regardless of match quality
- if any citation in the matched row equals "kb:[UNVERIFIED]" or contains
  the literal token [UNVERIFIED], force escalation=true
```

---

## 3. Hallucination Gate Prompt

Use as a fast reviewer on generated text or structured output.

```
TASK: Check this draft for hallucination risk against pilot artifacts

Allowed verdicts:
- PASS
- BLOCK
- ESCALATE
- HARNESS_FAULT        # parse/tool failure, corpus unreadable, linter error

Verdict priority when multiple rules fire:
HARNESS_FAULT > BLOCK > ESCALATE > PASS
Return only the highest-priority status. Lower-priority triggers may still be
named in violated_rule_ids or reason.

Rules:
- BLOCK if the draft invents facts, citations, tools, IDs, or payload structure.
- BLOCK if any citation matches "kb:[UNVERIFIED]" or contains [UNVERIFIED].
- BLOCK if any tool name is outside the union of tools_called in
  golden_corpus.jsonl, unless handoff_spec.md section 10
  (intelligent_field_evaluations) authorizes it explicitly.
- ESCALATE if evidence is absent, ambiguous, or only implied.
- ESCALATE if the supporting corpus row has unverified=true or
  source starts with "placeholder_".
- ESCALATE if draft confidence is below handoff_spec section 13
  confidence_threshold (default 0.75 until pilot intake sets it).
- HARNESS_FAULT if the corpus, handoff_spec, or linter is unreadable
  or returns a non-enumerated exit code.
- PASS only if every non-trivial claim is grounded in handoff_spec or
  golden_corpus AND the grounding row has unverified=false.

Output:
- status
- violated_rule_ids
- concise reason
```

---

## 4. Handoff Editor Prompt

Use when revising `handoff_spec.md`.

```
TASK: Edit pilot handoff without scope drift

Allowed sources:
- current ceal/pilots/<pilot>/handoff_spec.md
- ceal/pilots/<pilot>/pilot_profile.yaml
- ceal/pilots/<pilot>/ledger.jsonl
- ceal/docs/planning/SELF_REVIEW.md

Authoritative gate: ceal/tools/handoff_lint.py

Required section anchors (must be preserved exactly, in any order):
pilot_identity, customer_ask, translated_requirement, scope,
source_of_truth_integrations, schema_contract, affected_artifacts,
payload_examples, error_handling, intelligent_field_evaluations,
downstream_impact_analysis, severity_and_acceptance,
hallucination_guardrails, rollback_plan, signoff

Constraints:
- preserve all 15 required section anchors (HTML-comment tags, exact text)
- keep [UNVERIFIED] markers unless evidence exists in the allowed sources
- do not add new schema fields, affected artifacts, signers, or thresholds
  unless explicitly supported
- any schema_contract leaf-path add/remove whose symmetric-difference
  delta vs. prior revision exceeds 25 percent auto-returns ESCALATE
  (matches handoff_lint.py DELTA_ESCALATION_THRESHOLD_PCT)
- every mutation must correspond to a ledger.jsonl event reference;
  if the ledger writer is not yet built (ledger.jsonl is empty), return
  ESCALATE with reason="ledger_writer_unbuilt"
- if the requested change exceeds documented scope, return ESCALATE

Deliver:
- revised section text only
- minimal diff style
- ledger event stub (event_type, artifact_ref) OR the ledger_writer_unbuilt escalation
```

---

## 5. Corpus Expansion Prompt

Use when adding or reviewing new golden-corpus rows.

```
TASK: Propose a new golden corpus row

Fit the new row to the existing schema and case taxonomy:
- happy
- edge
- adversarial

Required fields on every row:
case_id, case_type, input, expected{intent, citations, tools_called, escalation},
source, unverified

Required additional field on adversarial rows:
adversarial_rationale in {prior_failure_case, fragile_integration_touchpoint,
downstream_cascade_probe}

Constraints:
- reuse existing intent names when possible
- reuse existing tool names when possible (allowed set = union of tools_called
  across current rows)
- mark source honestly; source="placeholder_*" is only legal when the row is a
  schema fixture for tests and unverified=true is also set
- if the case requires a new intent, tool, or citation shape, call that out
  explicitly instead of silently extending the schema
- a corpus mutation must correspond to a ledger.jsonl event
  (event_type="golden_corpus_row_added"); if the ledger writer is not yet
  built, return ESCALATE with reason="ledger_writer_unbuilt"

Return:
- candidate JSON object
- why it belongs
- whether schema/version bump is required
- ledger event stub OR the ledger_writer_unbuilt escalation
```

---

## Usage Notes

- Use the general runtime prompts when the task spans multiple subsystems.
- Use this file when the task is mostly about pilot alignment and token efficiency.
- **Verdict priority hard rule.** If multiple triggers fire, return exactly one
  top-level status using `HARNESS_FAULT > BLOCK > ESCALATE > PASS`.
- **Placeholder-corpus hard rule.** While `ceal/pilots/<pilot>/golden_corpus.jsonl`
  contains any row with `unverified: true`, every prompt in this pack defaults to
  `ESCALATE` on ambiguity. A `PASS` verdict requires every referenced row to
  satisfy `unverified: false` AND `source` not starting with `placeholder_`.
- Paths in this file are repo-relative from the workspace root
  (`C:\Users\joshb\Documents\Claude\Projects\Ceal`). Downstream callers must
  resolve `ceal/...`, not `pilots/...`.
