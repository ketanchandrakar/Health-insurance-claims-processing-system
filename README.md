
# Health Insurance Claims Processing System

Automates the work an insurance claims clerk does today: read a member's
uploaded medical documents, check them against their policy, and decide
whether to approve, partially approve, reject, or escalate the claim — with a
full, reconstructable explanation for every decision.



## Design philosophy

The single most important decision: **the LLM reads, deterministic code
decides.** A vision model does the one thing only it can do — extract structured
data from handwritten, stamped, blurry documents. Every money decision (is it
covered, waiting periods, co-pay, limits) is plain, testable, deterministic
code driven entirely by `policy_terms.json`. This keeps decisions explainable
and reproducible, and keeps the LLM's unreliability quarantined to extraction.

Components are cleanly separated. Each agent does one job behind a typed
contract and hands a result back to the orchestrator; agents never call each
other. The orchestrator is the only thing that knows the order, owns the trace,
and wraps every step in `try/except` so a component failure degrades the run
instead of crashing it.

## Architecture

```
React SPA  --POST /claims/evaluate-->  Flask backend
                                         └── Orchestrator (sequences agents, owns trace + try/except)
                                               ├── validator        intake checks
                                               ├── doc_verifier      Gate 1: right documents present?
                                               ├── extractor         vision LLM -> structured JSON (+ fixture seam)
                                               ├── consistency       Gate 2: same patient across docs?
                                               ├── adjudicator       deterministic policy rules engine
                                               ├── fraud             same-day / monthly / high-value signals
                                               └── synthesizer       final decision + confidence
                                         reads: policy_terms.json · vision LLM · in-memory claims history
```

Flow: validate → Gate 1 → extract → Gate 2 → adjudicate → fraud → synthesize.
Any check that can stop the claim (invalid, wrong docs, patient mismatch,
policy violation) exits *before* money is calculated. Fraud can only escalate a
provisional APPROVED/PARTIAL to MANUAL_REVIEW. The final decision always carries
a trace and a confidence score, even when a component was skipped.

## Tech stack

- **Backend:** Python, Flask, Pydantic
- **Frontend:** React
- **Extraction:** vision LLM 
- **Observability:** Langfuse — mirrors the in-app trace to spans. The in-app
  trace returned in the API response is the source of truth; Langfuse is the
  production-observability layer, not a replacement.
- **Concurrency:** per-document extraction fans out via `ThreadPoolExecutor`
  (I/O-bound LLM calls; Flask views stay synchronous).

## Repository structure

```
claims-system/
├── README.md
├── DECISIONS.md            # running log of design choices + trade-offs
├── .gitignore
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── __init__.py     # Flask app factory
│   │   ├── main.py         # entrypoint
│   │   ├── models.py       # domain models — the contract spine (frozen first)
│   │   ├── policy.py       # loads/indexes policy_terms.json + members
│   │   ├── orchestrator.py # control loop, trace, try/except
│   │   ├── trace.py        # TraceEvent collector
│   │   └── agents/         # validator, doc_verifier, extractor, consistency,
│   │       │               #   adjudicator, fraud, synthesizer
│   ├── data/               # policy_terms.json, test_cases.json
│   ├── fixtures/           # per-test-case extracted payloads (deterministic eval)
│   ├── tests/              # pytest: one file per agent + the 12 eval cases
│   └── eval/               # run_eval.py -> report over all 12 cases
└── frontend/               # React: submit form, decision card, trace viewer
```

## The 12 test cases drive the build

| Case | Tests | Owner component |
|------|-------|-----------------|
| TC001 | Wrong document type, specific message | doc_verifier (Gate 1) |
| TC002 | Unreadable document, ask for re-upload | extractor → doc_verifier |
| TC003 | Documents for different patients | consistency (Gate 2) |
| TC004 | Clean approval, 10% co-pay → ₹1,350 | adjudicator |
| TC005 | Diabetes within waiting period | adjudicator |
| TC006 | Dental partial, cosmetic excluded → ₹8,000 | adjudicator (line items) |
| TC007 | MRI without pre-auth | adjudicator |
| TC008 | Per-claim limit exceeded | adjudicator |
| TC009 | Multiple same-day claims → manual review | fraud |
| TC010 | Network discount before co-pay → ₹3,240 | adjudicator (calc order) |
| TC011 | Component failure, graceful degradation | orchestrator |
| TC012 | Excluded treatment (obesity) | adjudicator |

## Setup

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add OPENAI_API_KEY and Langfuse keys
python -m app.main            # serves on http://localhost:8000
curl localhost:8000/health    # {"status":"ok"}
```

Frontend: added in a later commit (see build order).

## Testing

```bash
cd backend && pytest -q
```


