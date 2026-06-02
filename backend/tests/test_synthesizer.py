"""Tests for agents.synthesizer — decision precedence and confidence model."""
from app.agents.synthesizer import synthesize
from app.models import (
    AdjudicationResult,
    ConsistencyResult,
    Decision,
    DecisionStatus,
    DocCheckResult,
    FraudResult,
    RejectionReason,
    TraceEvent,
    TraceStatus,
    ValidationResult,
)


def _trace(*events: tuple[str, TraceStatus]) -> list[TraceEvent]:
    return [
        TraceEvent(component=comp, status=status, summary=f"{comp}:{status.value}")
        for comp, status in events
    ]


def _clean_trace() -> list[TraceEvent]:
    comps = ["validator", "doc_verifier", "extractor", "consistency", "adjudicator", "fraud"]
    return _trace(*[(c, TraceStatus.OK) for c in comps])


def _ok_adjudication(decision=DecisionStatus.APPROVED, amount=1350.0) -> AdjudicationResult:
    return AdjudicationResult(decision=decision, approved_amount=amount)


def test_clean_run_full_confidence():
    result = synthesize(
        ValidationResult(ok=True),
        DocCheckResult(passed=True),
        ConsistencyResult(consistent=True),
        _ok_adjudication(),
        FraudResult(),
        degraded=False,
        trace=_clean_trace(),
    )
    assert result.status == DecisionStatus.APPROVED
    assert result.confidence == 0.95


def test_tc011_three_bad_events_below_0_6():
    # Extractor DEGRADED + consistency SKIPPED + adjudicator SKIPPED → 3 × −0.15
    trace = _trace(
        ("validator", TraceStatus.OK),
        ("doc_verifier", TraceStatus.OK),
        ("extractor", TraceStatus.DEGRADED),
        ("consistency", TraceStatus.SKIPPED),
        ("adjudicator", TraceStatus.SKIPPED),
        ("fraud", TraceStatus.OK),
    )
    result = synthesize(
        ValidationResult(ok=True),
        DocCheckResult(passed=True),
        ConsistencyResult(consistent=True),
        _ok_adjudication(),
        FraudResult(),
        degraded=True,
        trace=trace,
    )
    assert result.confidence < 0.60
    assert result.confidence == 0.50
    assert result.recommend_manual_review is True


def test_tc012_clean_rejection_high_confidence():
    # Clean REJECTED with no degraded events → confidence stays at 0.95
    result = synthesize(
        ValidationResult(ok=True),
        DocCheckResult(passed=True),
        ConsistencyResult(consistent=True),
        AdjudicationResult(
            decision=DecisionStatus.REJECTED,
            reasons=[RejectionReason.EXCLUDED_CONDITION],
            notes="Diagnosis is excluded under the policy",
        ),
        FraudResult(),
        degraded=False,
        trace=_clean_trace(),
    )
    assert result.status == DecisionStatus.REJECTED
    assert result.confidence > 0.90
    assert result.confidence == 0.95


def test_fraud_escalates_approved_to_manual_review():
    result = synthesize(
        ValidationResult(ok=True),
        DocCheckResult(passed=True),
        ConsistencyResult(consistent=True),
        _ok_adjudication(decision=DecisionStatus.APPROVED),
        FraudResult(signals=["Same-day activity"], escalate_to_review=True),
        degraded=False,
        trace=_clean_trace(),
    )
    assert result.status == DecisionStatus.MANUAL_REVIEW
    assert result.recommend_manual_review is True


def test_consistency_warning_reduces_confidence():
    # Consistency passed (consistent=True) but had warnings → -0.10
    trace = [
        TraceEvent(
            component="consistency",
            status=TraceStatus.OK,
            summary="consistency:OK",
            detail={"consistent": True, "warnings": ["Name near-match (88%): ..."]}
        )
    ]
    result = synthesize(
        ValidationResult(ok=True),
        DocCheckResult(passed=True),
        ConsistencyResult(consistent=True),
        _ok_adjudication(),
        FraudResult(),
        degraded=False,
        trace=trace,
    )
    assert result.confidence == 0.85  # 0.95 - 0.10


def test_consistency_no_warnings_full_confidence():
    trace = [
        TraceEvent(
            component="consistency",
            status=TraceStatus.OK,
            summary="consistency:OK",
            detail={"consistent": True, "warnings": []}
        )
    ]
    result = synthesize(
        ValidationResult(ok=True),
        DocCheckResult(passed=True),
        ConsistencyResult(consistent=True),
        _ok_adjudication(),
        FraudResult(),
        degraded=False,
        trace=trace,
    )
    assert result.confidence == 0.95  # no penalty


def test_partial_doc_reduces_confidence():
    # Two PARTIAL docs → 0.95 - 2×0.05 = 0.85
    trace = [
        TraceEvent(
            component="extractor",
            status=TraceStatus.OK,
            summary="extractor:OK",
            detail={"count": 2, "unreadable_ids": [], "partial_ids": ["f1", "f2"]},
        )
    ]
    result = synthesize(
        ValidationResult(ok=True),
        DocCheckResult(passed=True),
        ConsistencyResult(consistent=True),
        _ok_adjudication(),
        FraudResult(),
        degraded=False,
        trace=trace,
    )
    assert result.confidence == 0.85


def test_validation_failure_takes_precedence():
    # Validation failed but adjudication says APPROVED — validation must win
    result = synthesize(
        ValidationResult(ok=False, failures=[RejectionReason.MEMBER_NOT_FOUND],
                         message="Member not found"),
        DocCheckResult(passed=True),
        ConsistencyResult(consistent=True),
        _ok_adjudication(decision=DecisionStatus.APPROVED),
        FraudResult(),
        degraded=False,
        trace=_clean_trace(),
    )
    assert result.status == DecisionStatus.REJECTED
    assert RejectionReason.MEMBER_NOT_FOUND in result.rejection_reasons
