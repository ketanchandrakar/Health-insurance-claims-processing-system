"""Tests for agents.adjudicator — guard logic and financial calculation."""
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
    LineItem,
    LineItemClassification,
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
    # TC007: DIAGNOSTIC, ₹15 000 >= ₹10 000 threshold, no pre_auth_number → REJECTED
    claim = _claim(
        member_id="EMP007",
        claim_category=ClaimCategory.DIAGNOSTIC,
        treatment_date=date(2024, 11, 2),
        claimed_amount=15000.0,
    )
    result = adjudicate(_docs("Suspected Lumbar Disc Herniation"), claim, policy)
    assert result.decision == DecisionStatus.REJECTED
    assert RejectionReason.PRE_AUTH_MISSING in result.reasons


def test_pre_auth_provided_bypasses_rejection(policy):
    # Same claim as TC007 but WITH a pre_auth_number — must NOT be rejected for pre-auth
    claim = _claim(
        member_id="EMP007",
        claim_category=ClaimCategory.DIAGNOSTIC,
        treatment_date=date(2024, 11, 2),
        claimed_amount=15000.0,
        pre_auth_number="PA-2024-00123",
    )
    result = adjudicate(_docs("Suspected Lumbar Disc Herniation"), claim, policy)
    assert RejectionReason.PRE_AUTH_MISSING not in result.reasons


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


# ---------------------------------------------------------------------------
# Financial calculation tests (Commit 6)
# ---------------------------------------------------------------------------

def _docs_with_items(diagnosis: str | None, items: list[tuple[str, float]]) -> list[ExtractedDoc]:
    line_items = [LineItem(description=desc, amount=amt) for desc, amt in items]
    return [ExtractedDoc(
        file_id="f1",
        doc_type=DocumentType.HOSPITAL_BILL,
        diagnosis=diagnosis,
        line_items=line_items,
        total_amount=sum(amt for _, amt in items),
        doc_confidence=0.95,
        status=ExtractedDocStatus.OK,
    )]


def test_tc004_clean_consultation(policy):
    # TC004: EMP001, City Clinic (non-network), ₹1 500 CONSULTATION, 10% co-pay
    # 1500 × (1 - 0%) × (1 - 10%) = 1350
    claim = _claim(
        member_id="EMP001",
        treatment_date=date(2024, 11, 1),
        claimed_amount=1500.0,
        hospital_name="City Clinic, Bengaluru",
    )
    docs = _docs_with_items("Fever", [
        ("Consultation Fee", 1000.0),
        ("CBC Test", 300.0),
        ("Dengue NS1 Test", 200.0),
    ])
    result = adjudicate(docs, claim, policy)
    assert result.decision == DecisionStatus.APPROVED
    assert result.approved_amount == 1350.0


def test_tc006_dental_partial(policy):
    # TC006: EMP002, DENTAL, Root Canal (covered) + Teeth Whitening (excluded)
    # Only Root Canal ₹8 000 approved — 0% copay, 0% network discount
    claim = _claim(
        member_id="EMP002",
        claim_category=ClaimCategory.DENTAL,
        treatment_date=date(2024, 10, 15),
        claimed_amount=12000.0,
        hospital_name="Smile Dental Clinic",
    )
    docs = _docs_with_items(None, [
        ("Root Canal Treatment", 8000.0),
        ("Teeth Whitening", 4000.0),
    ])
    result = adjudicate(docs, claim, policy)
    assert result.decision == DecisionStatus.PARTIAL
    assert result.approved_amount == 8000.0

    by_desc = {li.description: li for li in result.line_item_breakdown}
    assert by_desc["Root Canal Treatment"].classification == LineItemClassification.COVERED
    assert by_desc["Teeth Whitening"].classification == LineItemClassification.EXCLUDED


def test_tc010_network_discount(policy):
    # TC010: EMP010, Apollo Hospitals (network), ₹4 500 CONSULTATION
    # 4500 × (1 - 20%) × (1 - 10%) = 3240
    claim = _claim(
        member_id="EMP010",
        treatment_date=date(2024, 11, 3),
        claimed_amount=4500.0,
        hospital_name="Apollo Hospitals",
    )
    docs = _docs_with_items("Fever", [
        ("Consultation Fee", 1500.0),
        ("Medicines", 3000.0),
    ])
    result = adjudicate(docs, claim, policy)
    assert result.decision == DecisionStatus.APPROVED
    assert result.approved_amount == 3240.0
    assert len(result.calc_trace) == 2
    assert "20%" in result.calc_trace[0].label   # network discount applied first
    assert "10%" in result.calc_trace[1].label   # copay applied second
