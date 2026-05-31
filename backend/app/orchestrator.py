"""Orchestrator — owns the pipeline execution order and trace assembly.

Sequence:
    validate -> doc_verify (Gate 1) -> extract -> consistency (Gate 2)
             -> adjudicate -> fraud -> synthesize

Every step is wrapped in try/except. A component crash produces a DEGRADED
trace event and sets degraded=True, which the synthesizer uses to lower
confidence and flag manual review. The pipeline never raises.

The optional `fixtures` param maps file_id -> ExtractedDoc dict for the
eval path (deterministic, no LLM calls). Real uploads leave it None.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from app.models import (
    AdjudicationResult,
    ClaimRequest,
    ConsistencyResult,
    Decision,
    DecisionStatus,
    DocCheckResult,
    ExtractedDoc,
    ExtractedDocStatus,
    FraudResult,
    TraceStatus,
    ValidationResult,
)
from app.policy import Policy
from app.trace import TraceCollector

from app.agents.validator import validate
from app.agents.doc_verifier import verify_documents
from app.agents.extractor import extract
from app.agents.consistency import check_consistency
from app.agents.adjudicator import adjudicate
from app.agents.fraud import detect_fraud
from app.agents.synthesizer import synthesize


def _ms(t0: float) -> int:
    return int((time.monotonic() - t0) * 1000)


def evaluate(
    claim: ClaimRequest,
    policy: Policy,
    fixtures: dict | None = None,
    today: date | None = None,
) -> Decision:
    collector = TraceCollector()
    degraded = False

    # typed placeholders — synthesizer always receives complete objects
    validation = ValidationResult(ok=True)
    doc_check = DocCheckResult(passed=True)
    consistency = ConsistencyResult(consistent=True)
    extracted: list[ExtractedDoc] = []
    adjudication = AdjudicationResult(decision=DecisionStatus.APPROVED, approved_amount=0.0)
    fraud = FraudResult()

    # ------------------------------------------------------------------
    # 1. Intake validation
    # ------------------------------------------------------------------
    t0 = time.monotonic()
    try:
        validation = validate(claim, policy, today=today)
        s = TraceStatus.OK if validation.ok else TraceStatus.FAILED
        collector.record(
            "validator", s,
            "Intake validation passed" if validation.ok else f"Validation failed: {validation.message}",
            validation.model_dump(), _ms(t0),
        )
    except Exception as exc:
        degraded = True
        collector.degraded("validator", f"Validator error: {exc}", duration_ms=_ms(t0))

    # ------------------------------------------------------------------
    # 2. Document type check — Gate 1 (pre-extraction, type check only)
    # ------------------------------------------------------------------
    t0 = time.monotonic()
    try:
        uploaded = [d.actual_type for d in claim.documents if d.actual_type]
        doc_check = verify_documents(uploaded, claim.claim_category, policy, [])
        s = TraceStatus.OK if doc_check.passed else TraceStatus.FAILED
        collector.record(
            "doc_verifier", s,
            "Document types OK" if doc_check.passed else f"Document check failed: {doc_check.message}",
            doc_check.model_dump(), _ms(t0),
        )
    except Exception as exc:
        degraded = True
        collector.degraded("doc_verifier", f"Doc verifier error: {exc}", duration_ms=_ms(t0))

    if not doc_check.passed:
        for comp in ("extractor", "consistency", "adjudicator", "fraud"):
            collector.record(comp, TraceStatus.SKIPPED, "Skipped — document gate failed")
        return synthesize(validation, doc_check, consistency, adjudication, fraud,
                          degraded, collector.events)

    # ------------------------------------------------------------------
    # 3. Extraction — parallel per document
    # ------------------------------------------------------------------
    t0 = time.monotonic()
    try:
        if claim.simulate_component_failure:
            raise RuntimeError("Simulated extraction failure (TC011)")

        def _extract_one(doc: object) -> ExtractedDoc:
            fixture = (fixtures or {}).get(doc.file_id)  # type: ignore[union-attr]
            return extract(doc, fixture=fixture)  # type: ignore[arg-type]

        with ThreadPoolExecutor() as pool:
            extracted = list(pool.map(_extract_one, claim.documents))

        unreadable = [d.file_id for d in extracted if d.status == ExtractedDocStatus.UNREADABLE]
        collector.record(
            "extractor", TraceStatus.OK,
            f"Extracted {len(extracted)} doc(s), {len(unreadable)} unreadable",
            {"count": len(extracted), "unreadable_ids": unreadable}, _ms(t0),
        )

        # Re-run doc check now that we know which files couldn't be read
        if unreadable:
            uploaded = [d.actual_type for d in claim.documents if d.actual_type]
            doc_check = verify_documents(uploaded, claim.claim_category, policy, unreadable)
            if not doc_check.passed:
                for comp in ("consistency", "adjudicator", "fraud"):
                    collector.record(comp, TraceStatus.SKIPPED, "Skipped — unreadable doc gate")
                return synthesize(validation, doc_check, consistency, adjudication, fraud,
                                  degraded, collector.events)
    except Exception as exc:
        degraded = True
        collector.degraded("extractor", f"Extraction error: {exc}", duration_ms=_ms(t0))
        # Consistency and adjudicator need extracted docs to do useful work.
        # Skip them so their OK status doesn't inflate confidence.
        for comp in ("consistency", "adjudicator"):
            collector.record(comp, TraceStatus.SKIPPED, "Skipped — extraction failed")

    # ------------------------------------------------------------------
    # 4. Cross-document consistency — Gate 2 (skipped if extraction failed)
    # ------------------------------------------------------------------
    if extracted:
        t0 = time.monotonic()
        try:
            consistency = check_consistency(extracted)
            s = TraceStatus.OK if consistency.consistent else TraceStatus.FAILED
            collector.record(
                "consistency", s,
                "Consistency check passed" if consistency.consistent else f"Inconsistency: {consistency.message}",
                consistency.model_dump(), _ms(t0),
            )
        except Exception as exc:
            degraded = True
            collector.degraded("consistency", f"Consistency error: {exc}", duration_ms=_ms(t0))

        if not consistency.consistent:
            for comp in ("adjudicator", "fraud"):
                collector.record(comp, TraceStatus.SKIPPED, "Skipped — consistency gate failed")
            return synthesize(validation, doc_check, consistency, adjudication, fraud,
                              degraded, collector.events)

    # ------------------------------------------------------------------
    # 5. Adjudication (skipped if extraction failed)
    # ------------------------------------------------------------------
    if extracted:
        t0 = time.monotonic()
        try:
            adjudication = adjudicate(extracted, claim, policy)
            collector.record(
                "adjudicator", TraceStatus.OK,
                f"Adjudication: {adjudication.decision.value}"
                + (f", approved ₹{adjudication.approved_amount}" if adjudication.approved_amount is not None else ""),
                adjudication.model_dump(), _ms(t0),
            )
        except Exception as exc:
            degraded = True
            adjudication = AdjudicationResult(
                decision=DecisionStatus.MANUAL_REVIEW,
                notes=f"Adjudicator error: {exc}",
            )
            collector.degraded("adjudicator", f"Adjudicator error: {exc}", duration_ms=_ms(t0))

    # ------------------------------------------------------------------
    # 6. Fraud detection
    # ------------------------------------------------------------------
    t0 = time.monotonic()
    try:
        fraud = detect_fraud(claim, policy)
        collector.record(
            "fraud", TraceStatus.OK,
            f"Fraud: {len(fraud.signals)} signal(s), escalate={fraud.escalate_to_review}",
            fraud.model_dump(), _ms(t0),
        )
    except Exception as exc:
        degraded = True
        collector.degraded("fraud", f"Fraud detector error: {exc}", duration_ms=_ms(t0))

    # ------------------------------------------------------------------
    # 7. Synthesize final decision
    # ------------------------------------------------------------------
    return synthesize(validation, doc_check, consistency, adjudication, fraud,
                      degraded, collector.events)
