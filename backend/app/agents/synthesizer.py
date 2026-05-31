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
  6. degraded=True              -> recommend_manual_review=True

Confidence model:
  Start at 0.95 for a clean full run.
  -0.20 per UNREADABLE doc (read from extractor trace detail)
  -0.15 per DEGRADED or SKIPPED trace event
  Floor at 0.10
"""
from app.models import (
    AdjudicationResult,
    ConsistencyResult,
    Decision,
    DecisionStatus,
    DocCheckResult,
    FraudResult,
    TraceEvent,
    TraceStatus,
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
    # ------------------------------------------------------------------
    # Decision precedence
    # ------------------------------------------------------------------
    if not validation.ok:
        return Decision(
            status=DecisionStatus.REJECTED,
            reason=validation.message or "Claim failed intake validation",
            confidence=_confidence(trace),
            rejection_reasons=validation.failures,
            recommend_manual_review=degraded,
            trace=trace,
        )

    if not doc_check.passed:
        return Decision(
            status=DecisionStatus.STOPPED,
            reason="Document check failed",
            confidence=_confidence(trace),
            message_to_member=doc_check.message,
            recommend_manual_review=degraded,
            trace=trace,
        )

    if not consistency.consistent:
        return Decision(
            status=DecisionStatus.STOPPED,
            reason="Documents belong to different patients",
            confidence=_confidence(trace),
            message_to_member=consistency.message,
            recommend_manual_review=degraded,
            trace=trace,
        )

    status = adjudication.decision
    if fraud.escalate_to_review:
        status = DecisionStatus.MANUAL_REVIEW

    reason = _reason(status, adjudication, fraud)

    return Decision(
        status=status,
        approved_amount=adjudication.approved_amount,
        reason=reason,
        confidence=_confidence(trace),
        rejection_reasons=adjudication.reasons,
        line_item_breakdown=adjudication.line_item_breakdown,
        recommend_manual_review=degraded or fraud.escalate_to_review,
        trace=trace,
    )


def _confidence(trace: list[TraceEvent]) -> float:
    score = 0.95

    for event in trace:
        if event.component == "extractor" and event.status == TraceStatus.OK:
            unreadable = len(event.detail.get("unreadable_ids", []))
            score -= 0.20 * unreadable

    for event in trace:
        if event.status in (TraceStatus.DEGRADED, TraceStatus.SKIPPED):
            score -= 0.15

    return max(0.10, round(score, 2))


def _reason(
    status: DecisionStatus,
    adjudication: AdjudicationResult,
    fraud: FraudResult,
) -> str:
    if status == DecisionStatus.MANUAL_REVIEW:
        if fraud.signals:
            return f"Flagged for manual review: {fraud.signals[0]}"
        return "Flagged for manual review"
    if status == DecisionStatus.REJECTED:
        return adjudication.notes or "Claim rejected"
    if status == DecisionStatus.PARTIAL:
        return adjudication.notes or "Partial approval — some line items excluded"
    if status == DecisionStatus.APPROVED:
        return adjudication.notes or "Claim approved"
    return status.value
