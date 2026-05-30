"""Decision synthesis + confidence.

Contract:
  synthesize(validation, doc_check, consistency, adjudication, fraud,
             degraded: bool, trace) -> Decision

Decision precedence (highest priority wins):
  1. validation.ok=False        -> REJECTED
  2. doc_check.passed=False     -> STOPPED  (message_to_member from doc_check)
  3. consistency.consistent=False -> STOPPED (message_to_member from consistency)
  4. adjudication.decision      -> APPROVED / PARTIAL / REJECTED
  5. fraud.escalate_to_review   -> override to MANUAL_REVIEW
  6. degraded=True              -> recommend_manual_review=True, lower confidence

Full confidence model yet to be added 
"""
from app.models import (
    AdjudicationResult,
    ClaimRequest,
    ConsistencyResult,
    Decision,
    DecisionStatus,
    DocCheckResult,
    FraudResult,
    TraceEvent,
    ValidationResult,
)


def synthesize(
    validation: ValidationResult,
    doc_check: DocCheckResult,
    consistency: ConsistencyResult,
    adjudication: AdjudicationResult,
    fraud: FraudResult,
    degraded: bool,
    trace: list[TraceEvent],
) -> Decision:
    if not validation.ok:
        return Decision(
            status=DecisionStatus.REJECTED,
            reason=validation.message or "Claim failed intake validation",
            confidence=0.95,
            rejection_reasons=validation.failures,
            trace=trace,
        )

    if not doc_check.passed:
        return Decision(
            status=DecisionStatus.STOPPED,
            reason="Document check failed",
            confidence=0.95,
            message_to_member=doc_check.message,
            trace=trace,
        )

    if not consistency.consistent:
        return Decision(
            status=DecisionStatus.STOPPED,
            reason="Documents belong to different patients",
            confidence=0.95,
            message_to_member=consistency.message,
            trace=trace,
        )

    status = adjudication.decision
    if fraud.escalate_to_review:
        status = DecisionStatus.MANUAL_REVIEW

    confidence = 0.95
    if degraded:
        confidence -= 0.15
    confidence = max(0.10, confidence)

    return Decision(
        status=status,
        approved_amount=adjudication.approved_amount,
        reason=adjudication.notes or status.value,
        confidence=confidence,
        rejection_reasons=adjudication.reasons,
        line_item_breakdown=adjudication.line_item_breakdown,
        recommend_manual_review=degraded or fraud.escalate_to_review,
        trace=trace,
    )
