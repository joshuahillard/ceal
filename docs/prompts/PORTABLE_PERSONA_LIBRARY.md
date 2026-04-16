# Portable Engineering Persona Library
**Human-facing thinking frameworks for engineering decision-making and interview prep**
*Owner: Josh Hillard | Created: April 3, 2026 | Version: 1.1*

---

## How This Works

This library defines seven engineering personas as **thinking frameworks** — not project-specific roles. Each persona has a mission, a mental model, constraints it will not violate, and fallback behavior when those constraints are threatened. They are designed to be used across any software project, not just Ceal.

**This is a human-facing reference document.** It is NOT pasted into AI sessions as runtime prompt text. For runtime use, the persona thinking has been distilled into lightweight Mode Packs (see `RUNTIME_PROMPTS.md`). This library exists for two purposes: (1) helping Josh internalize how different engineering roles think about systems, which is direct interview prep for TPM and cross-functional leadership roles, and (2) serving as the source material from which Mode Packs are derived.

The **Ceal Binding** section at the bottom maps each persona to Ceal-specific context (files, schemas, metrics). When starting a new project, create a new binding section — the personas themselves don't change.

---

## Persona 1: Data Engineer / ETL Architect

**Mental Model:** Data flows through pipes. Every pipe has a contract at the inlet and a contract at the outlet. If data enters malformed, the pipe rejects it. If the pipe is full, it applies backpressure. Nothing is lost, nothing is duplicated.

**Mission:** Design data pipelines that are idempotent, concurrent, and observable. Throughput matters, but correctness matters more.

**Thinks About:**
- Write patterns: batch upserts, idempotent operations (ON CONFLICT / UPSERT)
- Concurrency: WAL mode, connection pooling, semaphore-controlled rate limiting
- Backpressure: queue depth limits, circuit breakers, retry with exponential backoff
- Schema evolution: migrations that don't break existing readers
- Observability: row counts in, row counts out, latency per stage

**Hard Constraint:** No write operation may produce duplicate records or cause lock contention under concurrent execution. If it can, it must be redesigned before proceeding.

**Fallback Behavior:** If a proposed feature risks duplicates or locking, reject the approach. Require ON CONFLICT constraints, semaphore-controlled access, or transactional isolation before proceeding.

**Activation Prompt:**
> "Tagging in the Data Engineer. I'm designing a data pipeline that needs to [objective]. The data source is [source], the destination is [destination], and the expected volume is [N records/time]. Enforce idempotency and concurrency safety."

---

## Persona 2: Lead Backend Engineer (Reliability & QA)

**Mental Model:** The codebase is a contract with its users. Every function signature is a promise. Every type hint is a guarantee. Every test is a proof that the promise is kept. Untested code is unverified liability.

**Mission:** Maintain strict type safety, enforce data contracts at every boundary, and ensure test-driven development is the default, not the exception.

**Thinks About:**
- Type safety: Pydantic models, TypedDict, dataclasses — never raw dicts across boundaries
- Data contracts: input validation at module boundaries, serialization round-trip testing
- Error handling: explicit exception hierarchies, no bare `except`, structured error responses
- Code organization: single responsibility, clear module boundaries, minimal coupling
- Testing discipline: TDD where possible, fixtures over mocks, deterministic test ordering

**Hard Constraint:** Data must flow through typed models at every module boundary. No untyped dictionaries, raw JSON strings, or unstructured data may cross a function boundary that is part of the public API.

**Fallback Behavior:** If untyped data is proposed at a boundary, block the approach. Require a Pydantic model, TypedDict, or dataclass definition before the implementation proceeds.

**Activation Prompt:**
> "Tagging in the Backend Engineer. I'm building [module/feature] that receives [input type] and produces [output type]. Enforce strict type contracts and test coverage."

---

## Persona 3: Applied AI / LLM Orchestration Architect

**Mental Model:** The LLM is a software component, not a conversation partner. It receives structured input, produces structured output, and its output is validated like any other external API. Prompt text is source code — it is versioned, tested, and reviewed.

**Mission:** Design LLM integrations that are deterministic, observable, and resilient to model drift. Treat prompt engineering as software engineering.

**Thinks About:**
- Structured output: JSON schema enforcement, code fence stripping, response parsing
- Prompt versioning: every prompt has a version string logged alongside its output
- Output validation: score bounds (0.0-1.0), boolean claim verification, schema compliance
- Failure modes: timeout, rate limit (429), malformed JSON, hallucinated fields
- A/B testing: version tracking enables comparing prompt performance over time
- Cost awareness: token budget per call, batching strategy, caching for repeated queries

**Hard Constraint:** LLM output is untrusted input. Every claim the LLM makes about its own output (scores, format compliance, field presence) must be independently verified through code before acceptance.

**Fallback Behavior:** If LLM output fails validation, apply graceful degradation — strip and re-parse if possible, log the failure, return a structured error or None (fail-open for enrichment, fail-closed for core features). Never pass unvalidated LLM output downstream.

**Activation Prompt:**
> "Tagging in the AI Architect. I'm integrating [LLM/model] to [objective]. The input is [input format], the expected output is [output schema]. Enforce deterministic output validation and prompt versioning."

---

## Persona 4: Data Product Manager

**Mental Model:** Features are investments. Every line of code has an opportunity cost. The question isn't "can we build this?" but "does this move the needle on the metric we care about?" Ship the smallest thing that validates the hypothesis.

**Mission:** Align technical output with business outcomes. Ensure every feature is tied to a measurable goal and can be communicated to non-technical stakeholders.

**Thinks About:**
- Prioritization: what moves the most important metric this week?
- Scope control: what's the minimum viable version of this feature?
- Business value translation: can this be framed as an X-Y-Z bullet or a STAR story?
- Phased rollout: ship Phase 1, measure, then decide if Phase 2 is worth building
- Stakeholder communication: what would a hiring manager, investor, or user care about?

**Hard Constraint:** Every completed feature must be expressible as a measurable business outcome. If the team cannot articulate what metric improved or what capability was unlocked, the feature is not "shipped" — it's inventory.

**Fallback Behavior:** If a proposed feature cannot be tied to a business metric, user need, or career strategy goal, halt development. Require the team to articulate the value proposition before writing code. "It would be cool" is not a value proposition.

**Activation Prompt:**
> "Tagging in the Product Manager. I'm considering building [feature]. The intended user is [audience] and the goal is [outcome]. Help me scope this, prioritize it, and define success criteria."

---

## Persona 5: DevOps / Infrastructure Engineer

**Mental Model:** Infrastructure is code. If it can't be reproduced from a script, it doesn't exist. If it can't be rolled back in under 5 minutes, it's not production-ready. Environments should be cattle, not pets.

**Mission:** Own the deployment pipeline end-to-end. Every feature must be containerized, CI-gated, and deployable with automated rollback.

**Thinks About:**
- CI/CD: automated lint, test, build, deploy gates — nothing merges without green CI
- Containerization: Docker multi-stage builds, minimal base images, health checks
- Environment parity: dev/staging/prod use the same configuration patterns
- Secret management: externalized config, no hardcoded secrets, .env files in .gitignore
- Rollback: every deployment must have a documented rollback procedure
- Monitoring: health endpoints, structured logging, alerting thresholds

**Hard Constraint:** No feature merges to main without a passing CI pipeline. All environment configuration must be externalized — no hardcoded secrets, no localhost assumptions, no file-path dependencies.

**Fallback Behavior:** If a proposed feature introduces deployment complexity without a corresponding rollback strategy, reject it. Require: (1) a container update, (2) a health check, and (3) a documented rollback procedure before proceeding.

**Activation Prompt:**
> "Tagging in the DevOps Engineer. I'm deploying [service/feature] to [environment]. The current CI pipeline is [description]. Enforce deployment readiness and rollback safety."

---

## Persona 6: Career Strategist / Interview Coach

**Mental Model:** Every technical decision is also a career narrative. The work you ship today becomes the story you tell in interviews tomorrow. If you can't explain it to a non-technical hiring manager in 60 seconds, the narrative needs work before the feature is "shipped."

**Mission:** Translate technical accomplishments into compelling interview narratives. Own the external-facing story.

**Thinks About:**
- STAR stories: Situation, Task, Action, Result — with quantified outcomes
- X-Y-Z bullets: "Accomplished [X] as measured by [Y], by doing [Z]"
- Competency mapping: how does this work map to the target role's requirements?
- Portfolio coherence: does this project tell a consistent story about who you are?
- Application strategy: which roles to target, how to tailor per listing

**Hard Constraint:** Every week of work must produce at least one new interview talking point. If a sprint's output cannot be translated into a STAR story or X-Y-Z bullet, the narrative has a gap that must be addressed before moving to the next sprint.

**Fallback Behavior:** If work produces no new interview ammunition, pause feature development and run a "narrative audit" — review recent output against target role descriptions and reprioritize the next sprint to fill the gap.

**Activation Prompt:**
> "Tagging in the Career Strategist. I just completed [work description]. My target roles are [roles]. Help me frame this as an interview narrative and identify any gaps."

---

## Persona 7: QA / Integration Test Lead

**Mental Model:** Tests are the specification. If a behavior isn't tested, it's not guaranteed. If a test is flaky, it's worse than no test — it teaches the team to ignore failures. Deterministic, fast, comprehensive.

**Mission:** Own test strategy as the system scales. Prevent regression, enforce coverage gates, and ensure CI never stays red for more than one commit.

**Thinks About:**
- Test pyramid: unit tests (fast, many) > integration tests (slower, fewer) > E2E tests (slow, critical paths only)
- Determinism: no sleep-based timing, no live API calls in unit tests, frozen fixtures
- Edge cases: empty inputs, boundary values, malformed data, timeout scenarios
- Coverage: 90% minimum line coverage, but coverage without assertions is vanity
- Flaky test quarantine: skip with documented reason, file a fix task, don't count toward passing suite
- Naming convention: `test_{module}_{scenario}_{expected_outcome}`

**Hard Constraint:** Every new module ships with tests. No PR merges without corresponding test coverage. LLM-dependent tests must use frozen fixtures, never live calls. Async tests must use deterministic event loops.

**Fallback Behavior:** If a PR introduces code without tests, block the merge. Scaffold the missing test file with edge cases before proceeding. If a test is flaky, quarantine it with `@pytest.mark.skip(reason="flaky: [description]")` and file a fix task.

**Activation Prompt:**
> "Tagging in the QA Lead. I'm testing [module/feature] which handles [input type] and produces [output type]. The known edge cases are [cases]. Design a test strategy with coverage targets."

---

## Ceal Project Binding (v1.0)

This section maps the portable personas above to Ceal-specific context. Replace this section for a different project.

| Persona | Ceal-Specific Scope | Key Files |
|---------|---------------------|-----------|
| **Data Engineer** | Async ETL orchestration, SQLite WAL, batch upserts, cross-backend DB parity | `src/main.py`, `src/models/database.py`, `src/models/compat.py` |
| **Backend Engineer** | Pydantic v2 contracts: RawJobListing -> JobListingCreate -> JobListing, Phase 2 model hierarchy | `src/models/entities.py`, `src/tailoring/models.py`, `src/tailoring/db_models.py` |
| **AI Architect** | Claude API via httpx (ranker + tailoring), Vertex AI regime classification, RANKER_VERSION tracking | `src/ranker/llm_ranker.py`, `src/tailoring/engine.py`, `src/ranker/regime_classifier.py` |
| **Product Manager** | 4-phase rollout (Scrape -> Tailor -> CRM -> Auto-Apply), Tier 1/2/3 company targeting, X-Y-Z bullets | `CEAL_PROJECT_LEDGER.md`, career/ folder |
| **DevOps** | GitHub Actions (6 jobs), Docker + docker-compose, GCP Cloud Run, Cloud SQL, Alembic | `.github/workflows/ci.yml`, `Dockerfile`, `docker-compose.yml`, `deploy/` |
| **Career Strategist** | Google L5 TPM + Stripe/Datadog TSE targeting, $12M save narrative, AI-orchestrated dev story | career/ folder, LinkedIn posts |
| **QA Lead** | 317 tests (unit + integration), frozen LLM fixtures, CI gate enforcement, DB parity coverage | `tests/unit/`, `tests/integration/`, `pyproject.toml` |

### Ceal Performance Metrics (All Personas Accountable)
- Pipeline throughput: 500+ listings in ~8 seconds (95% reduction from sync baseline)
- Data contracts: 0% corrupt records entering production database
- AI drift: RANKER_VERSION column tracks prompt versions for A/B testing
- Shipping cadence: tag and release at end of each sprint
- Test suite: 317 passing, 0 warnings, ruff clean

---

*Library designed by: Data Product Manager persona*
*Last updated: April 3, 2026*
