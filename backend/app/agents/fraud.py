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
    signals: list[str] = []
    date_str = str(claim.treatment_date)
    month_str = date_str[:7]  # "YYYY-MM"

    # Same-day check: count prior claims on the same date + this one
    same_day = [c for c in claim.claims_history if c.get("date") == date_str]
    if len(same_day) + 1 > policy.same_day_claims_limit:
        signals.append(
            f"Unusual same-day activity: {len(same_day) + 1} claims on {date_str}"
        )

    # Monthly volume check
    monthly = [c for c in claim.claims_history if c.get("date", "").startswith(month_str)]
    if len(monthly) + 1 >= policy.monthly_claims_limit:
        signals.append(
            f"High monthly volume: {len(monthly) + 1} claims in {month_str}"
        )

    # High-value check
    if claim.claimed_amount >= policy.high_value_threshold:
        signals.append(
            f"High-value claim: ₹{claim.claimed_amount:,.0f} "
            f"(threshold ₹{policy.high_value_threshold:,.0f})"
        )

    return FraudResult(signals=signals, escalate_to_review=len(signals) > 0)
