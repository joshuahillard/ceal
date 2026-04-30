# Hand-off Spec: acme-corp pilot

Binds to: Maven_Implementation_OS_Master_Prompt.md v1.2 Deliverable 2.

Every customer-surface reference in this document carries an
`artifact_ref` with `type`, `value`, and `verification_method`. Claims
without a resolvable reference are tagged `[UNVERIFIED]` inline. This
file is the source document; the linter at `tools/handoff_lint.py`
consumes it and rejects any handoff missing a required section anchor,
missing `artifact_ref` fields, invalid severity, or an unauthorized
schema-contract delta greater than 25 percent.

Section anchors below are machine-addressable via HTML comment tags.
Display text under each anchor is for human readers; only the anchor
tag is required by the linter.

---

<!-- section: pilot_identity -->
## 1. Pilot identity block

- customer_id: `acme-corp` [UNVERIFIED]
- pilot_id: `acme-corp-csx-q2` [UNVERIFIED]
- maven_environment: `staging` [UNVERIFIED]
- fde_assigned: `<to_be_named>` [UNVERIFIED]
- target_go_live_date: `<to_be_named>` [UNVERIFIED]

---

<!-- section: customer_ask -->
## 2. Customer ask verbatim

Placeholder text. The real verbatim ask from the customer business
sponsor goes here, quoted, unedited. [UNVERIFIED]

---

<!-- section: translated_requirement -->
## 3. Translated requirement

Placeholder implementation-language restatement of the verbatim ask.
Must name the intelligent field evaluation the agent will emit and
the customer-system read/write set the agent touches. [UNVERIFIED]

---

<!-- section: scope -->
## 4. In scope / out of scope

In scope:
- Placeholder in-scope item 1 [UNVERIFIED]
- Placeholder in-scope item 2 [UNVERIFIED]

Out of scope:
- Placeholder out-of-scope item 1 [UNVERIFIED]
- Placeholder out-of-scope item 2 [UNVERIFIED]

---

<!-- section: source_of_truth_integrations -->
## 5. Source-of-truth integrations

Placeholder list of customer systems with:

- integration name
- auth method
- OAuth scopes
- rate limits (requests per minute, burst)
- sandbox availability (yes/no + environment URL)

All values [UNVERIFIED] pending pilot intake.

---

<!-- section: schema_contract -->
## 6. Schema contract

The block below is parsed by `handoff_lint.py`; its normalized digest
is used for the 25-percent scope-change-delta rule. Every field carries
the customer object name, the field name, the Pydantic-style type, and
an `[UNVERIFIED]` marker until a real schema is supplied.

```yaml
schema_contract:
  ticket:
    id:               { type: "string",    source: "[UNVERIFIED]" }
    subject:          { type: "string",    source: "[UNVERIFIED]" }
    body:             { type: "string",    source: "[UNVERIFIED]" }
    priority:         { type: "enum[low,medium,high,urgent]", source: "[UNVERIFIED]" }
    status:           { type: "enum[open,pending,solved,closed]", source: "[UNVERIFIED]" }
    requester_email:  { type: "string",    source: "[UNVERIFIED]" }
  account:
    id:               { type: "string",    source: "[UNVERIFIED]" }
    name:             { type: "string",    source: "[UNVERIFIED]" }
    tier:             { type: "enum[free,starter,growth,enterprise]", source: "[UNVERIFIED]" }
  kb_article:
    id:               { type: "string",    source: "[UNVERIFIED]" }
    title:            { type: "string",    source: "[UNVERIFIED]" }
    body:             { type: "string",    source: "[UNVERIFIED]" }
    last_updated_utc: { type: "iso8601",   source: "[UNVERIFIED]" }
  intent_label:
    id:               { type: "string",    source: "[UNVERIFIED]" }
    category:         { type: "string",    source: "[UNVERIFIED]" }
```

---

<!-- section: affected_artifacts -->
## 7. Affected artifacts

The block below lists every customer-surface reference this handoff
touches. Every entry carries `type`, `value`, and `verification_method`
or the linter rejects the handoff as BLOCK.

```yaml
affected_artifacts:
  - type: "api_endpoint"
    value: "[UNVERIFIED]://placeholder.acme-corp.example/api/v1/tickets"
    verification_method: "curl with pilot sandbox token returns 200 plus schema_contract.ticket fields"
  - type: "schema_field"
    value: "ticket.priority"
    verification_method: "Zendesk admin UI displays field with enum values matching schema_contract.ticket.priority"
  - type: "workflow_rule"
    value: "[UNVERIFIED]://acme-corp.example/workflows/routing-rule-42"
    verification_method: "Metadata API returns status=active with trigger=RecordAfterSave on Case object"
```

---

<!-- section: payload_examples -->
## 8. Payload examples

Minimum three redacted samples per object (happy, edge, malformed).
All samples below are placeholders pending customer PII-redacted
ticket history supply. [UNVERIFIED]

```json
{
  "happy":     { "ticket": { "id": "PLACEHOLDER-001", "priority": "medium" } },
  "edge":      { "ticket": { "id": "PLACEHOLDER-002", "priority": "urgent", "body": "<8kb payload>" } },
  "malformed": { "ticket": { "id": "PLACEHOLDER-003", "priority": null } }
}
```

---

<!-- section: error_handling -->
## 9. Error handling logic

For each integration declared in section source_of_truth_integrations:

- retry policy: [UNVERIFIED] (proposed default: exponential backoff, base 1s, cap 30s)
- backoff: [UNVERIFIED]
- circuit-breaker threshold: [UNVERIFIED] (proposed default: 5 failures in 60s window)
- escalation behavior on exhaustion: [UNVERIFIED]

---

<!-- section: intelligent_field_evaluations -->
## 10. Intelligent field evaluations

For each computed field the agent emits on this pilot:

- field_name: `[UNVERIFIED]`
- input_fields: `[UNVERIFIED]`
- transform_logic: `[UNVERIFIED]`
- expected_output_range: `[UNVERIFIED]`
- downstream_consumers: `[UNVERIFIED]` (see section downstream_impact_analysis)

---

<!-- section: downstream_impact_analysis -->
## 11. Downstream impact analysis

For every intelligent field evaluation named in section
intelligent_field_evaluations, declare what breaks in the customer
stack if that field is wrong, missing, or stale. Every entry must
reference the consuming customer surface by `artifact_ref.value`.

- consumer: `[UNVERIFIED]`
  - failure_if_wrong: `[UNVERIFIED]`
  - failure_if_missing: `[UNVERIFIED]`
  - failure_if_stale: `[UNVERIFIED]`

---

<!-- section: severity_and_acceptance -->
## 12. Severity and acceptance check

```yaml
severity: "major"            # allowed: critical | major | minor | info
acceptance_check:
  condition: "[UNVERIFIED]"
  evidence_path: "pilots/acme-corp/evidence/[UNVERIFIED].md"
```

---

<!-- section: hallucination_guardrails -->
## 13. Hallucination guardrails

- citation_requirement: every generated answer must cite at least one
  `kb_article.id` from section schema_contract. [UNVERIFIED]
- confidence_threshold: `[UNVERIFIED]` (proposed default: 0.75)
- human_escalation_trigger: confidence below threshold OR no citation
  found OR adversarial case flag raised by safety classifier.
  [UNVERIFIED]

---

<!-- section: rollback_plan -->
## 14. Rollback plan

Ordered rollback steps with named authorizer per step. Every step
must reference the `artifact_ref.value` being reverted.

1. `[UNVERIFIED]` (authorizer: `[UNVERIFIED]`)
2. `[UNVERIFIED]` (authorizer: `[UNVERIFIED]`)
3. `[UNVERIFIED]` (authorizer: `[UNVERIFIED]`)

---

<!-- section: signoff -->
## 15. Sign-off and scope-change authorization

```yaml
signoff:
  customer_engineering:    { signer: "[UNVERIFIED]", signed_ts_utc: null }
  customer_business_sponsor: { signer: "[UNVERIFIED]", signed_ts_utc: null }
  maven_fde:               { signer: "[UNVERIFIED]", signed_ts_utc: null }
  maven_im:                { signer: "[UNVERIFIED]", signed_ts_utc: null }
scope_change_authorized_by: null   # set to signer identity when 25-percent-delta rule trips
```

---

End of handoff_spec.md. The linter expects exactly the fifteen section
anchors above, in any order, each with non-empty body content.
