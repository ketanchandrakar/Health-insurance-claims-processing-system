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

from langfuse import get_client, propagate_attributes

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


def _finish(decision: Decision, lf_root) -> Decision:
    lf_root.update(output={
        "status": decision.status.value,
        "approved_amount": decision.approved_amount,
        "rejection_reasons": [r.value for r in decision.rejection_reasons],
        "reason": decision.reason,
        "confidence": decision.confidence,
        "recommend_manual_review": decision.recommend_manual_review,
        "message_to_member": decision.message_to_member,
    })
    return decision


def evaluate(
    claim: ClaimRequest,
    policy: Policy,
    fixtures: dict | None = None,
    today: date | None = None,
) -> Decision:
    langfuse = get_client()

    try:
        with langfuse.start_as_current_observation(
            as_type="span",
            name="claims-pipeline",
            input={
                "member_id": claim.member_id,
                "category": claim.claim_category.value,
                "claimed_amount": claim.claimed_amount,
                "doc_count": len(claim.documents),
            },
        ) as lf_root:
            with propagate_attributes(
                user_id=str(claim.member_id),
                trace_name="claims-pipeline",
                tags=[claim.claim_category.value],
            ):
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
                with langfuse.start_as_current_observation(
                    as_type="span", name="validator",
                    input={"member_id": claim.member_id},
                ) as lf_span:
                    try:
                        validation = validate(claim, policy, today=today)
                        s = TraceStatus.OK if validation.ok else TraceStatus.FAILED
                        lf_span.update(output={
                            "ok": validation.ok,
                            "failures": [r.value for r in validation.failures],
                            "message": validation.message,
                        })
                        collector.record(
                            "validator", s,
                            "Intake validation passed" if validation.ok else f"Validation failed: {validation.message}",
                            validation.model_dump(), _ms(t0),
                        )
                    except Exception as exc:
                        degraded = True
                        lf_span.update(metadata={"error": str(exc)})
                        collector.degraded("validator", f"Validator error: {exc}", duration_ms=_ms(t0))

                if not validation.ok:
                    for comp in ("doc_verifier", "extractor", "consistency", "adjudicator", "fraud"):
                        collector.record(comp, TraceStatus.SKIPPED, "Skipped — validation failed")
                    return _finish(
                        synthesize(validation, doc_check, consistency, adjudication, fraud,
                                   degraded, collector.events),
                        lf_root,
                    )

                # ------------------------------------------------------------------
                # 2. Document type check — Gate 1 (pre-extraction, type check only)
                # ------------------------------------------------------------------
                t0 = time.monotonic()
                with langfuse.start_as_current_observation(
                    as_type="span", name="doc_verifier",
                ) as lf_span:
                    try:
                        uploaded = [d.actual_type for d in claim.documents if d.actual_type]
                        doc_check = verify_documents(uploaded, claim.claim_category, policy, [])
                        s = TraceStatus.OK if doc_check.passed else TraceStatus.FAILED
                        lf_span.update(
                            input={"uploaded_types": [t.value if t else None for t in uploaded]},
                            output={
                                "passed": doc_check.passed,
                                "missing_types": [t.value for t in doc_check.missing_types],
                                "wrong_types": [t.value for t in doc_check.wrong_types],
                                "unreadable_files": doc_check.unreadable_files,
                                "message": doc_check.message,
                            },
                        )
                        collector.record(
                            "doc_verifier", s,
                            "Document types OK" if doc_check.passed else f"Document check failed: {doc_check.message}",
                            doc_check.model_dump(), _ms(t0),
                        )
                    except Exception as exc:
                        degraded = True
                        lf_span.update(metadata={"error": str(exc)})
                        collector.degraded("doc_verifier", f"Doc verifier error: {exc}", duration_ms=_ms(t0))

                if not doc_check.passed:
                    for comp in ("extractor", "consistency", "adjudicator", "fraud"):
                        collector.record(comp, TraceStatus.SKIPPED, "Skipped — document gate failed")
                    return _finish(
                        synthesize(validation, doc_check, consistency, adjudication, fraud,
                                   degraded, collector.events),
                        lf_root,
                    )

                # ------------------------------------------------------------------
                # 3. Extraction — parallel per document
                # ------------------------------------------------------------------
                t0 = time.monotonic()
                with langfuse.start_as_current_observation(
                    as_type="generation",
                    name="extractor",
                    model="gemini-2.5-flash-lite",
                    input={"doc_count": len(claim.documents)},
                ) as lf_span:
                    try:
                        if claim.simulate_component_failure:
                            raise RuntimeError("Simulated extraction failure (TC011)")

                        def _extract_one(doc: object) -> ExtractedDoc:
                            fixture = (fixtures or {}).get(doc.file_id)  # type: ignore[union-attr]
                            return extract(doc, fixture=fixture)  # type: ignore[arg-type]

                        with ThreadPoolExecutor() as pool:
                            extracted = list(pool.map(_extract_one, claim.documents))

                        unreadable = [d.file_id for d in extracted if d.status == ExtractedDocStatus.UNREADABLE]
                        partial = [d.file_id for d in extracted if d.status == ExtractedDocStatus.PARTIAL]
                        lf_span.update(output={
                            "count": len(extracted),
                            "unreadable_ids": unreadable,
                            "partial_ids": partial,
                            "docs": [
                                {
                                    "file_id": d.file_id,
                                    "doc_type": d.doc_type.value,
                                    "status": d.status.value,
                                    "doc_confidence": d.doc_confidence,
                                    "patient_name": d.patient_name,
                                    "diagnosis": d.diagnosis,
                                    "total_amount": d.total_amount,
                                    "field_confidences": d.field_confidences,
                                }
                                for d in extracted
                            ],
                        })
                        collector.record(
                            "extractor", TraceStatus.OK,
                            f"Extracted {len(extracted)} doc(s), {len(unreadable)} unreadable",
                            {"count": len(extracted), "unreadable_ids": unreadable, "partial_ids": partial}, _ms(t0),
                        )

                        # Re-run doc check now that we know which files couldn't be read
                        if unreadable:
                            uploaded = [d.actual_type for d in claim.documents if d.actual_type]
                            doc_check = verify_documents(uploaded, claim.claim_category, policy, unreadable)
                            if not doc_check.passed:
                                for comp in ("consistency", "adjudicator", "fraud"):
                                    collector.record(comp, TraceStatus.SKIPPED, "Skipped — unreadable doc gate")
                                return _finish(
                                    synthesize(validation, doc_check, consistency, adjudication, fraud,
                                               degraded, collector.events),
                                    lf_root,
                                )
                    except Exception as exc:
                        degraded = True
                        lf_span.update(metadata={"error": str(exc)})
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
                    with langfuse.start_as_current_observation(
                        as_type="span", name="consistency",
                    ) as lf_span:
                        try:
                            consistency = check_consistency(extracted, claim_date=claim.treatment_date)
                            s = TraceStatus.OK if consistency.consistent else TraceStatus.FAILED
                            lf_span.update(output={
                                "consistent": consistency.consistent,
                                "mismatches": consistency.mismatches,
                                "message": consistency.message,
                            })
                            collector.record(
                                "consistency", s,
                                "Consistency check passed" if consistency.consistent else f"Inconsistency: {consistency.message}",
                                consistency.model_dump(), _ms(t0),
                            )
                        except Exception as exc:
                            degraded = True
                            lf_span.update(metadata={"error": str(exc)})
                            collector.degraded("consistency", f"Consistency error: {exc}", duration_ms=_ms(t0))

                    if not consistency.consistent:
                        for comp in ("adjudicator", "fraud"):
                            collector.record(comp, TraceStatus.SKIPPED, "Skipped — consistency gate failed")
                        return _finish(
                            synthesize(validation, doc_check, consistency, adjudication, fraud,
                                       degraded, collector.events),
                            lf_root,
                        )

                # ------------------------------------------------------------------
                # 5. Adjudication (skipped if extraction failed)
                # ------------------------------------------------------------------
                if extracted:
                    t0 = time.monotonic()
                    with langfuse.start_as_current_observation(
                        as_type="span", name="adjudicator",
                    ) as lf_span:
                        try:
                            adjudication = adjudicate(extracted, claim, policy)
                            lf_span.update(output={
                                "decision": adjudication.decision.value,
                                "approved_amount": adjudication.approved_amount,
                                "rejection_reasons": [r.value for r in adjudication.reasons],
                                "eligible_from": adjudication.eligible_from.isoformat() if adjudication.eligible_from else None,
                                "calc_trace": [s.model_dump() for s in adjudication.calc_trace],
                                "line_item_breakdown": [
                                    {
                                        "description": li.description,
                                        "amount": li.amount,
                                        "classification": li.classification.value,
                                        "reason": li.reason,
                                    }
                                    for li in adjudication.line_item_breakdown
                                ],
                                "notes": adjudication.notes,
                            })
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
                            lf_span.update(metadata={"error": str(exc)})
                            collector.degraded("adjudicator", f"Adjudicator error: {exc}", duration_ms=_ms(t0))

                # ------------------------------------------------------------------
                # 6. Fraud detection
                # ------------------------------------------------------------------
                t0 = time.monotonic()
                with langfuse.start_as_current_observation(
                    as_type="span", name="fraud",
                ) as lf_span:
                    try:
                        fraud = detect_fraud(claim, policy)
                        lf_span.update(output={
                            "signals": fraud.signals,
                            "signal_count": len(fraud.signals),
                            "escalate_to_review": fraud.escalate_to_review,
                        })
                        collector.record(
                            "fraud", TraceStatus.OK,
                            f"Fraud: {len(fraud.signals)} signal(s), escalate={fraud.escalate_to_review}",
                            fraud.model_dump(), _ms(t0),
                        )
                    except Exception as exc:
                        degraded = True
                        lf_span.update(metadata={"error": str(exc)})
                        collector.degraded("fraud", f"Fraud detector error: {exc}", duration_ms=_ms(t0))

                # ------------------------------------------------------------------
                # 7. Synthesize final decision
                # ------------------------------------------------------------------
                return _finish(
                    synthesize(validation, doc_check, consistency, adjudication, fraud,
                               degraded, collector.events),
                    lf_root,
                )

    finally:
        langfuse.flush()
