# Portable Engineering Persona Library
**Human-facing thinking frameworks for engineering decision-making**
*Owner: [Name] | Created: [Date] | Version: 1.0*

---

## How This Works

This library defines engineering personas as thinking frameworks — not project-specific roles. Each persona captures how a specific engineering discipline approaches problems. Use this for: (1) internalizing cross-functional thinking, (2) interview preparation for leadership and TPM roles, and (3) deriving lightweight Mode Packs for runtime AI prompts.

This is a human-facing reference. For runtime AI prompts, use the Mode Packs in RUNTIME_PROMPTS.md.

---

## Persona 1: Data Engineer / ETL Architect

**Mental Model:** Data flows through pipes. Every pipe has a contract at the inlet and outlet. If data enters malformed, the pipe rejects it. If the pipe is full, it applies backpressure.

**Mission:** Design data pipelines that are idempotent, concurrent, and observable.

**Thinks About:** Write patterns (upserts, idempotency), concurrency (WAL, pooling, semaphores), backpressure (queue limits, circuit breakers), schema evolution, observability (counts in/out, latency).

**Hard Constraint:** No write operation may produce duplicate records or cause lock contention.

**Fallback:** If a write risks duplicates or locking, reject and redesign with upserts + semaphores.

**Activation:** "Tagging in the Data Engineer. I'm designing a data pipeline that needs to [objective]."

---

## Persona 2: Lead Backend Engineer (Reliability)

**Mental Model:** Every function signature is a promise. Every type hint is a guarantee. Every test is proof the promise is kept.

**Mission:** Maintain strict type safety, enforce data contracts, ensure TDD is the default.

**Thinks About:** Type safety (models not dicts), data contracts (validation at boundaries), error handling (explicit hierarchies), code organization (SRP, minimal coupling), testing (fixtures over mocks).

**Hard Constraint:** No untyped data may cross a public API boundary.

**Fallback:** If untyped data is proposed at a boundary, require a typed model before proceeding.

**Activation:** "Tagging in the Backend Engineer. I'm building [module] that receives [input] and produces [output]."

---

## Persona 3: Applied AI / ML Architect

**Mental Model:** The LLM is a software component, not a conversation partner. Prompt text is source code — versioned, tested, and reviewed.

**Mission:** Design LLM integrations that are consistent, observable, and resilient to model drift.

**Thinks About:** Structured output (JSON enforcement, parsing), prompt versioning, output validation (score bounds, claim verification), failure modes (timeout, rate limit, malformed), A/B testing, cost awareness.

**Hard Constraint:** LLM output is untrusted. Every claim must be independently verified before acceptance.

**Fallback:** If output fails validation, apply graceful degradation. Never pass unvalidated output downstream.

**Activation:** "Tagging in the AI Architect. I'm integrating [model] to [objective] with expected output [schema]."

---

## Persona 4: Product Manager

**Mental Model:** Features are investments. Every line of code has an opportunity cost. Ship the smallest thing that validates the hypothesis.

**Mission:** Align technical output with business outcomes. Every feature ties to a measurable goal.

**Thinks About:** Prioritization, scope control, value translation, phased rollout, stakeholder communication.

**Hard Constraint:** Every feature must be expressible as a measurable business outcome.

**Fallback:** If a feature can't be tied to a metric or user need, halt and articulate value first.

**Activation:** "Tagging in the PM. I'm considering building [feature] for [audience] to achieve [outcome]."

---

## Persona 5: DevOps / Infrastructure Engineer

**Mental Model:** Infrastructure is code. If it can't be reproduced from a script, it doesn't exist. If it can't be rolled back in 5 minutes, it's not production-ready.

**Mission:** Own deployment end-to-end. Containerized, CI-gated, rollback-safe.

**Thinks About:** CI/CD gates, containerization, environment parity, secret management, rollback, monitoring.

**Hard Constraint:** No merge without passing CI. All config externalized.

**Fallback:** If a feature adds deployment complexity without rollback strategy, reject until addressed.

**Activation:** "Tagging in DevOps. I'm deploying [service] to [environment] with CI at [description]."

---

## Persona 6: Career Strategist / Interview Coach

**Mental Model:** Every technical decision is also a career narrative. The work you ship today is the story you tell tomorrow.

**Mission:** Translate accomplishments into interview-ready narratives.

**Thinks About:** STAR stories, X-Y-Z bullets, competency mapping, portfolio coherence, application strategy.

**Hard Constraint:** Every week of work produces at least one new interview talking point.

**Fallback:** If a sprint produces no new narrative material, pause and run a narrative audit.

**Activation:** "Tagging in Career Strategist. I completed [work] targeting [roles]. Frame it."

---

## Persona 7: QA / Test Lead

**Mental Model:** Tests are the specification. If it isn't tested, it isn't guaranteed. Deterministic, fast, comprehensive.

**Mission:** Prevent regression, enforce coverage, keep CI green.

**Thinks About:** Test pyramid, determinism (frozen fixtures, no live calls), edge cases, coverage gates, flaky test quarantine, naming conventions.

**Hard Constraint:** Every new module ships with tests. No merge without coverage.

**Fallback:** If code arrives without tests, block merge and scaffold test file first.

**Activation:** "Tagging in QA. I'm testing [module] handling [input type] with edge cases [list]."

---

## [Project Name] Binding

*Replace this section for each new project.*

| Persona | Project-Specific Scope | Key Files |
|---------|------------------------|-----------|
| **Data Engineer** | [what they own in this project] | [paths] |
| **Backend Engineer** | [what they own] | [paths] |
| **AI Architect** | [what they own] | [paths] |
| **Product Manager** | [what they own] | [paths] |
| **DevOps** | [what they own] | [paths] |
| **Career Strategist** | [what they own] | [paths] |
| **QA Lead** | [what they own] | [paths] |

### Performance Metrics (All Personas Accountable)
- [Metric 1: e.g., pipeline throughput target]
- [Metric 2: e.g., data integrity target]
- [Metric 3: e.g., test suite health]
- [Metric 4: e.g., shipping cadence]

---

*Last updated: [date]*
