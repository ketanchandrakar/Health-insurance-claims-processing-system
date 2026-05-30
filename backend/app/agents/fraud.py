"""Fraud detection.

Contract:
  detect_fraud(claim, policy) -> FraudResult
Counts same-day and monthly claims from claim.claims_history and applies the
high-value threshold. Produces signals and escalate_to_review only — it can
push a decision to MANUAL_REVIEW but never approves or rejects (TC009).
"""
from app.models import ClaimRequest, FraudResult
from app.policy import Policy


def detect_fraud(claim: ClaimRequest, policy: Policy) -> FraudResult:
    #yet to implement
    return FraudResult()
