"""Tests for agents.adjudicator — guard logic.


"""
from datetime import date

import pytest

from app.agents.adjudicator import adjudicate
from app.models import (
    ClaimCategory,
    ClaimRequest,
    DecisionStatus,
    DocumentInput,
    DocumentType,
    ExtractedDoc,
    ExtractedDocStatus,
    RejectionReason,
)
from app.policy import load_policy


@pytest.fixture(scope="module")
def policy():
    return load_policy()


def _claim(**overrides) -> ClaimRequest:
    base = dict(
        member_id="EMP001",
        policy_id="PLUM_GHI_2024",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date=date(2024, 11, 1),
        claimed_amount=1500.0,
        documents=[DocumentInput(file_id="f1", file_name="bill.pdf", actual_type=DocumentType.HOSPITAL_BILL)],
    )
    base.update(overrides)
    return ClaimRequest(**base)


def _docs(diagnosis: str | None = None) -> list[ExtractedDoc]:
    return [ExtractedDoc(
        file_id="f1",
        doc_type=DocumentType.HOSPITAL_BILL,
        diagnosis=diagnosis,
        doc_confidence=0.95,
        status=ExtractedDocStatus.OK,
    )]


def test_clean_claim_passes_all_guards(policy):
    result = adjudicate(_docs("Fever"), _claim(), policy)
    assert result.decision == DecisionStatus.APPROVED


def test_waiting_period_rejected(policy):
    # TC005: EMP005 joined 2024-09-01, diabetes = 90 days → eligible 2024-11-30
    # treatment on 2024-10-15 is before eligibility
    claim = _claim(
        member_id="EMP005",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date=date(2024, 10, 15),
        claimed_amount=3000.0,
    )
    result = adjudicate(_docs("Type 2 Diabetes Mellitus"), claim, policy)
    assert result.decision == DecisionStatus.REJECTED
    assert RejectionReason.WAITING_PERIOD in result.reasons
    assert result.eligible_from == date(2024, 11, 30)


def test_exclusion_rejected(policy):
    # TC012: obesity diagnosis is excluded
    claim = _claim(
        member_id="EMP009",
        treatment_date=date(2024, 10, 18),
        claimed_amount=8000.0,
    )
    result = adjudicate(_docs("Morbid Obesity — BMI 37"), claim, policy)
    assert result.decision == DecisionStatus.REJECTED
    assert RejectionReason.EXCLUDED_CONDITION in result.reasons


def test_pre_auth_missing(policy):
    # TC007: DIAGNOSTIC, ₹15 000 >= ₹10 000 threshold → PRE_AUTH_MISSING
    claim = _claim(
        member_id="EMP007",
        claim_category=ClaimCategory.DIAGNOSTIC,
        treatment_date=date(2024, 11, 2),
        claimed_amount=15000.0,
    )
    result = adjudicate(_docs("Suspected Lumbar Disc Herniation"), claim, policy)
    assert result.decision == DecisionStatus.REJECTED
    assert RejectionReason.PRE_AUTH_MISSING in result.reasons


def test_per_claim_limit_exceeded(policy):
    # TC008: ₹7 500 > per_claim_limit ₹5 000
    claim = _claim(
        member_id="EMP003",
        treatment_date=date(2024, 10, 20),
        claimed_amount=7500.0,
    )
    result = adjudicate(_docs("Gastroenteritis"), claim, policy)
    assert result.decision == DecisionStatus.REJECTED
    assert RejectionReason.PER_CLAIM_EXCEEDED in result.reasons
    # Notes must state both amounts so the member understands the rejection
    assert "7,500" in result.notes
    assert "5,000" in result.notes


def test_guard_order_waiting_beats_exclusion(policy):
    # EMP005 (joined 2024-09-01) claims "Obesity treatment":
    #   - obesity_treatment waiting period = 365 days → eligible 2025-09-01
    #   - treatment on 2024-10-15 is before eligibility → guard 1 fires
    #   - "obesity" keyword also matches exclusions → guard 2 would also fire
    # Guard 1 (WAITING_PERIOD) must win over guard 2 (EXCLUDED_CONDITION)
    claim = _claim(
        member_id="EMP005",
        treatment_date=date(2024, 10, 15),
        claimed_amount=1000.0,
    )
    result = adjudicate(_docs("Obesity treatment consultation"), claim, policy)
    assert result.decision == DecisionStatus.REJECTED
    assert RejectionReason.WAITING_PERIOD in result.reasons
    assert RejectionReason.EXCLUDED_CONDITION not in result.reasons
