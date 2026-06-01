# Architecture Document

## Health Insurance Claims Processing System

---

## 1. Problem and Goals

An employee submits a health insurance claim by uploading medical documents and providing claim details. A human clerk currently reads those documents, checks them against the policy, and decides whether to approve, reject, or escalate. This system automates that work.

The system must:
- Accept a claim (member, category, amount, documents)
- Catch bad documents early with specific, actionable feedback
- Extract structured data from messy real-world documents (handwritten, stamped, photographed)
- Apply deterministic policy rules to reach a decision
- Return a full, reconstructable trace for every decision
- Never crash on component failure

---

## 2. High-Level Architecture

```
React SPA  ──POST /claims/evaluate──▶  Flask Backend
                                          │
                                   Orchestrator
                                   (owns pipeline + trace + try/except)
                                          │
                              ┌───────────┴───────────┐
                              │  Sequential pipeline   │
                              ├── validator            │  intake checks
                              ├── doc_verifier  ◀Gate1 │  right documents?
                              ├── extractor            │  vision LLM → JSON
                              ├── consistency   ◀Gate2 │  same patient?
                              ├── adjudicator          │  policy rules → decision
                              ├── fraud                │  escalation signals
                              └── synthesizer          │  final Decision
                                          │
                                   Langfuse (mirror)   observability
                                          │
                              reads: policy_terms.json · Gemini 2.5 Flash-Lite
```

The frontend sends a single HTTP request. The orchestrator sequences 7 agents, wraps each in `try/except`, and always returns a typed `Decision` — even when components fail.

---

## 3. Design Decisions

### D1 — LLM reads, deterministic code decides

The vision model (Gemini 2.5 Flash-Lite) does only one thing: extract structured data from document images. All claim decisions — waiting periods, exclusions, financial calculations, fraud signals — are deterministic Python driven by `policy_terms.json`.

**Why:** Money decisions must be explainable and reproducible. An LLM asked to decide end-to-end is non-deterministic and hard to audit. Quarantining the LLM to extraction keeps the decision path fully traceable and unit-testable.

**Trade-off:** Extraction errors can propagate into decisions. Mitigated by per-document `doc_confidence` scores that feed the final confidence and can trigger manual review.

### D2 — `per_claim_limit` is the binding hard cap; category sub-limits are annual aggregates

TC008 rejects a ₹7,500 consultation against a ₹5,000 per-claim limit. TC010 approves a ₹4,500 consultation — which exceeds the ₹2,000 consultation sub-limit. The only reading that satisfies both is: `per_claim_limit` is the single-claim hard cap; sub-limits are annual aggregates enforced only when YTD data is available.

### D3 — Fixture injection seam in the extractor

`extract(doc, fixture=None)` returns a fixture deterministically when provided (eval path), and calls the live LLM on uploaded bytes otherwise (UI path). This makes the 12 test cases fully reproducible without document content, while real uploads demonstrate live extraction.

### D4 — In-app trace is the source of truth; Langfuse mirrors it

Every API response contains a `trace: list[TraceEvent]` that an ops engineer can read to reconstruct exactly why any decision was made. Langfuse mirrors those events as spans for production observability, but is not the source of truth.

### D5 — Flask + ThreadPoolExecutor for parallel extraction

Only one place requires concurrency: extracting multiple documents simultaneously. These are I/O-bound LLM calls, so a thread pool provides the needed parallelism without adopting an async framework for the whole application.

---

## 4. Component Interactions

### Data flow

```
ClaimRequest (JSON)
  → validator        ValidationResult
  → doc_verifier     DocCheckResult       [Gate 1: if failed → STOPPED]
  → extractor        ExtractedDoc[]       [Gate: if UNREADABLE → STOPPED]
  → consistency      ConsistencyResult    [Gate 2: if failed → STOPPED]
  → adjudicator      AdjudicationResult
  → fraud            FraudResult
  → synthesizer      Decision             [always returned]
```

Gates 1 and 2 are hard stops. If `doc_verifier` fails, nothing downstream runs — not extraction, not adjudication. This is intentional: there is no point spending LLM tokens on documents that are the wrong type.

### Failure handling

Every agent call is wrapped in a `try/except` block in the orchestrator. A hard failure (LLM timeout, parse error) produces a `DEGRADED` trace event, reduces confidence, and sets `recommend_manual_review=True`. The pipeline continues to the next agent wherever possible.

### Agents do not call each other

Every agent is a pure function: it receives typed inputs, performs its work, and returns a typed result. The orchestrator is the only component that knows execution order. This makes each agent independently testable and replaceable.

---

## 5. Key Technical Choices

### Pydantic v2 for all data contracts

Every input and output is a Pydantic model. This gives us runtime validation at system boundaries, structured serialisation via `model_dump(mode="json")`, and frozen type definitions that prevent accidental coupling.

### Policy rules from JSON, never hardcoded

All rates, thresholds, limits, and exclusions live in `policy_terms.json`. The `Policy` class exposes typed accessors. There is no hardcoded numeric in any agent file. This means rule changes require only a JSON edit, not a code deployment.

### Multi-agent structure

The pipeline is a multi-agent system: seven specialized agents with clean contracts, orchestrated by a control loop. Each agent is independently testable, observable, and replaceable. This is the key architectural property that makes the system maintainable — agents can be upgraded (e.g., swap Gemini for a newer model) without touching the orchestrator or other agents.

### Confidence scoring

The synthesizer computes a confidence score in [0.10, 0.95] based on:
- −0.05 per PARTIAL extraction doc
- −0.20 per UNREADABLE doc
- −0.15 per DEGRADED/SKIPPED component
- −0.10 per consistency warning
- Floor: 0.10

This gives the ops team a calibrated signal for how much to trust a decision.

---

## 6. What Was Considered and Rejected

### End-to-end LLM decision

Asking the LLM to read documents and decide the claim in one shot. Rejected because: non-deterministic, hard to audit, impossible to unit test, and breaks when the LLM changes.

### Async (FastAPI + asyncio)

The one place that benefits from concurrency is per-document extraction, which is I/O-bound. A thread pool handles that. Adopting an async framework for the entire application would add complexity without meaningful benefit at current scale.

### External rules engine (Drools, OPA)

The policy rules are complex enough to warrant their own module but not complex enough to justify an external system. A Python module reading from a JSON file is sufficient, auditable, and deployable without additional infrastructure.

### Per-document LLM adjudication

Having the LLM also classify line items and apply exclusions. Rejected because line-item classification is a string-matching problem against a known list — exactly the kind of work deterministic code handles reliably and LLMs can hallucinate.

---

## 7. Limitations and 10x Scaling Plan

### Current limitations

| Limitation | Detail |
|-----------|--------|
| Synchronous Flask | Each request blocks a thread for the full pipeline duration (~2–5 s with LLM calls) |
| In-memory claims history | Fraud detection reads `claims_history` from the request body — no persistence across sessions |
| Static member roster in JSON | Members live in `policy_terms.json` as a flat array; adding a member requires editing the file and restarting the server. No CRUD API, no auth, no audit trail. The fraud detector's claims history is also passed in the request body — a client could send a falsified history. |
| Policy loaded once at startup | Works for a single process; breaks under horizontal scaling if policies need live updates |
| ThreadPoolExecutor per request | Fine for 3–5 documents; unbounded thread creation under high concurrency |
| No queue/retry for LLM calls | Gemini rate limit (15 RPM free tier) causes 429s under concurrent load |

### 10x scaling plan

**Extraction → async task queue**

Replace synchronous per-request extraction with a Celery + Redis task queue. The `/claims/evaluate` endpoint enqueues work and returns a `claim_id`. A `/claims/{id}/status` endpoint lets the client poll. This decouples request latency from LLM latency and allows rate-limited retries without blocking web workers.

```
POST /claims/evaluate  →  enqueue task  →  return {claim_id, status: "processing"}
GET  /claims/{id}      →  read result from Redis / DB
```

**Policy rules → Redis cache**

Load `policy_terms.json` into Redis at startup. Workers read from the cache. Live policy updates publish a cache-invalidation message; workers reload on next request.

**Member roster + claims history → PostgreSQL**

Replace the static JSON member array with a `members` table. Add a `claims` table for history. Fraud detection queries by `member_id` + date range server-side instead of trusting client-supplied history. Member onboarding becomes an API call, not a file edit.

**Horizontal scaling**

Stateless Flask workers behind a load balancer (Nginx / AWS ALB). Each worker reads the same Redis policy cache and writes to the same PostgreSQL instance. No shared in-process state.

**Extraction workers as a separate service**

At very high volume, LLM extraction becomes the bottleneck. Isolate it as a dedicated microservice with its own Celery queue, auto-scaling group, and rate-limiter that respects the Gemini quota. The orchestrator calls this service over HTTP instead of calling the extractor agent directly.

**Estimated capacity**

Current single-threaded Flask: ~20 concurrent claims before latency degrades.
With Celery + Redis + 4 extraction workers: ~500 claims/minute throughput, bounded by Gemini API quota.
With a paid Gemini tier and 10 workers: ~2,000 claims/minute.

---

## 8. Observability

Every `Decision` response contains a `trace: list[TraceEvent]` with:
- `component` — which agent produced this event
- `status` — OK / FAILED / SKIPPED / DEGRADED
- `summary` — one human-readable line
- `detail` — structured dict (amounts, patient names, signals, etc.)
- `duration_ms` — how long this component took

This is sufficient to reconstruct any decision from the API response alone. Langfuse mirrors these events as spans for dashboards and alerting — it is an operational convenience, not a dependency.

---

## 9. Testing Strategy

- **Unit tests (35):** One file per agent. Each agent's pure-function contract is tested in isolation with Pydantic model inputs. No mocking.
- **Eval harness:** Runs all 12 test cases via HTTP against the live server, injecting pre-built fixtures. Validates `status`, `approved_amount`, `rejection_reasons`, and `confidence`.
- **12/12 pass** as of 2026-06-01 (see `eval_report.md`).
