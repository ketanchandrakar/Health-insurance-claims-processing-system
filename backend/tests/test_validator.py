"""Tests for agents.validator — intake validation."""
import copy
from datetime import date, timedelta

import pytest

from app.agents.validator import validate
from app.models import ClaimCategory, ClaimRequest, DocumentInput, DocumentType, RejectionReason
from app.policy import Policy, load_policy


@pytest.fixture(scope="module")
def policy() -> Policy:
    return load_policy()


def _claim(**overrides) -> ClaimRequest:
    """Minimal valid claim; individual tests override what they need."""
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


def test_valid_claim(policy):
    # today is set just inside the 30-day window
    today = date(2024, 11, 1) + timedelta(days=5)
    result = validate(_claim(), policy, today=today)
    assert result.ok is True
    assert result.failures == []


def test_unknown_member(policy):
    today = date(2024, 11, 6)
    result = validate(_claim(member_id="EMP999"), policy, today=today)
    assert result.ok is False
    assert RejectionReason.MEMBER_NOT_FOUND in result.failures


def test_submission_too_late(policy):
    # 31 days after treatment — just past the 30-day deadline
    treatment = date(2024, 11, 1)
    today = treatment + timedelta(days=31)
    result = validate(_claim(treatment_date=treatment), policy, today=today)
    assert result.ok is False
    assert RejectionReason.SUBMISSION_DEADLINE_PASSED in result.failures


def test_below_minimum_amount(policy):
    today = date(2024, 11, 6)
    result = validate(_claim(claimed_amount=100.0), policy, today=today)
    assert result.ok is False
    assert RejectionReason.BELOW_MINIMUM_AMOUNT in result.failures


def test_multiple_failures_collected(policy):
    # Late submission AND below-minimum — both reasons must appear
    treatment = date(2024, 11, 1)
    today = treatment + timedelta(days=45)
    result = validate(_claim(treatment_date=treatment, claimed_amount=50.0), policy, today=today)
    assert result.ok is False
    assert RejectionReason.SUBMISSION_DEADLINE_PASSED in result.failures
    assert RejectionReason.BELOW_MINIMUM_AMOUNT in result.failures


def test_inactive_policy(policy):
    # Build a minimal policy dict with renewal_status overridden to EXPIRED
    data = copy.deepcopy(policy._d)
    data["policy_holder"]["renewal_status"] = "EXPIRED"
    inactive = Policy(data=data)

    today = date(2024, 11, 6)
    result = validate(_claim(), inactive, today=today)
    assert result.ok is False
    assert RejectionReason.POLICY_INACTIVE in result.failures
