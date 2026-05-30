# Health-insurance-claims-processing-system
Automates the work an insurance claims clerk does today: read a member's uploaded medical documents, check them against their policy, and decide whether to approve, partially approve, reject, or escalate the claim — with a full, reconstructable explanation for every decision.

LLD

claims-system/
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI app + /claims/evaluate
│   │   ├── models.py              # all Pydantic models (the contracts)
│   │   ├── orchestrator.py        # control loop, trace, try/except
│   │   ├── policy.py              # loads + indexes policy_terms.json
│   │   ├── trace.py               # TraceEvent + collector
│   │   └── agents/
│   │       ├── validator.py       # intake validation
│   │       ├── doc_verifier.py    # Gate 1
│   │       ├── extractor.py       # vision LLM + fixture seam
│   │       ├── consistency.py     # Gate 2
│   │       ├── adjudicator.py     # the rules engine
│   │       ├── fraud.py           # fraud signals
│   │       └── synthesizer.py     # final decision + confidence
│   ├── fixtures/                  # per-test-case extracted payloads
│   ├── tests/                     # pytest, one file per agent + 12 eval cases
│   └── eval/run_eval.py           # runs all 12, emits report
└── frontend/                      # React: SubmitForm, DecisionCard, TraceViewer