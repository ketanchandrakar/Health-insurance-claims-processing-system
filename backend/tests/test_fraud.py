"""Tests for agents.fraud — signal detection and escalation logic."""
from datetime import date

import pytest

from app.agents.fraud import detect_fraud
from app.models import ClaimCategory, ClaimRequest, DocumentInput, DocumentType
from app.policy import load_policy


@pytest.fixture(scope="module")
def policy():
    return load_policy()


def _claim(claimed_amount: float = 1500.0, claims_history: list | None = None) -> ClaimRequest:
    return ClaimRequest(
        member_id="EMP001",
        policy_id="PLUM_GHI_2024",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date=date(2024, 10, 30),
        claimed_amount=claimed_amount,
        documents=[DocumentInput(file_id="f1", file_name="bill.pdf", actual_type=DocumentType.HOSPITAL_BILL)],
        claims_history=claims_history or [],
    )


def test_tc009_same_day_signals(policy):
    # TC009: EMP008 has 3 prior claims on 2024-10-30, this is the 4th
    # 4 > same_day_claims_limit (2) → signal fires
    history = [
        {"claim_id": "CLM_0081", "date": "2024-10-30", "amount": 1200},
        {"claim_id": "CLM_0082", "date": "2024-10-30", "amount": 1800},
        {"claim_id": "CLM_0083", "date": "2024-10-30", "amount": 2100},
    ]
    result = detect_fraud(_claim(claimed_amount=4800.0, claims_history=history), policy)

    assert result.escalate_to_review is True
    assert len(result.signals) >= 1
    assert any("same-day" in s.lower() or "2024-10-30" in s for s in result.signals)


def test_no_fraud_signals(policy):
    result = detect_fraud(_claim(), policy)
    assert result.escalate_to_review is False
    assert result.signals == []


def test_monthly_limit_signal(policy):
    # 5 prior claims in same month + current = 6 >= monthly_claims_limit (6)
    history = [
        {"claim_id": f"CLM_{i}", "date": "2024-10-{:02d}".format(i + 1), "amount": 500}
        for i in range(5)
    ]
    result = detect_fraud(_claim(claims_history=history), policy)

    assert result.escalate_to_review is True
    assert any("monthly" in s.lower() for s in result.signals)


def test_high_value_signal(policy):
    # claimed_amount at exactly the high-value threshold (₹25 000)
    result = detect_fraud(_claim(claimed_amount=25000.0), policy)

    assert result.escalate_to_review is True
    assert any("high-value" in s.lower() or "25,000" in s for s in result.signals)
