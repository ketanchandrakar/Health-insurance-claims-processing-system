"""Policy — wraps policy_terms.json and exposes typed accessors.

All rule values (rates, thresholds, limits) live in the JSON. Agents must
never hardcode a number; they always call an accessor on the Policy object
passed to them by the orchestrator.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from app.models import ClaimCategory, DocumentType


_DATA_DIR = Path(__file__).parent.parent / "data"

_CATEGORY_KEY: dict[ClaimCategory, str] = {
    ClaimCategory.CONSULTATION: "consultation",
    ClaimCategory.DIAGNOSTIC: "diagnostic",
    ClaimCategory.PHARMACY: "pharmacy",
    ClaimCategory.DENTAL: "dental",
    ClaimCategory.VISION: "vision",
    ClaimCategory.ALTERNATIVE_MEDICINE: "alternative_medicine",
}


class Policy:
    def __init__(self, data: dict | None = None) -> None:
        if data is None:
            raw = (_DATA_DIR / "policy_terms.json").read_text(encoding="utf-8")
            data = json.loads(raw)
        self._d = data

    # -- identity / status ------------------------------------------------

    @property
    def policy_id(self) -> str:
        return self._d["policy_id"]

    def is_active(self) -> bool:
        return self._d["policy_holder"]["renewal_status"] == "ACTIVE"

    # -- members ----------------------------------------------------------

    def get_member(self, member_id: str) -> dict | None:
        for m in self._d.get("members", []):
            if m["member_id"] == member_id:
                return m
        return None

    # -- submission rules -------------------------------------------------

    @property
    def minimum_claim_amount(self) -> float:
        return float(self._d["submission_rules"]["minimum_claim_amount"])

    @property
    def submission_deadline_days(self) -> int:
        return int(self._d["submission_rules"]["deadline_days_from_treatment"])

    # -- coverage limits --------------------------------------------------

    @property
    def per_claim_limit(self) -> float:
        return float(self._d["coverage"]["per_claim_limit"])

    def _category_data(self, category: ClaimCategory) -> dict:
        return self._d["opd_categories"][_CATEGORY_KEY[category]]

    def copay_for_category(self, category: ClaimCategory) -> float:
        return self._category_data(category).get("copay_percent", 0) / 100.0

    def sub_limit_for_category(self, category: ClaimCategory) -> float:
        return float(self._category_data(category).get("sub_limit", 0))

    def network_discount_for_category(self, category: ClaimCategory) -> float:
        return self._category_data(category).get("network_discount_percent", 0) / 100.0

    @property
    def pre_auth_threshold(self) -> float:
        # Diagnostic category carries the threshold for high-value imaging
        return float(self._d["opd_categories"]["diagnostic"].get("pre_auth_threshold", 10000))

    # -- network hospitals ------------------------------------------------

    @property
    def network_hospitals(self) -> list[str]:
        return list(self._d.get("network_hospitals", []))

    def is_network_hospital(self, hospital_name: str | None) -> bool:
        if not hospital_name:
            return False
        name = hospital_name.lower()
        return any(name in h.lower() or h.lower() in name for h in self.network_hospitals)

    # -- waiting periods --------------------------------------------------

    def waiting_period_days(self, diagnosis: str | None) -> int:
        if not diagnosis:
            return self._d["waiting_periods"]["initial_waiting_period_days"]
        diag = diagnosis.lower()
        for condition, days in self._d["waiting_periods"]["specific_conditions"].items():
            if condition.replace("_", " ") in diag:
                return int(days)
        return self._d["waiting_periods"]["initial_waiting_period_days"]

    def eligible_from_date(self, member: dict, diagnosis: str | None) -> date:
        join = date.fromisoformat(member["join_date"])
        return join + timedelta(days=self.waiting_period_days(diagnosis))

    # -- exclusions -------------------------------------------------------

    def is_excluded(self, diagnosis: str | None) -> bool:
        if not diagnosis:
            return False
        diag = diagnosis.lower()
        return any(excl.lower() in diag for excl in self._d["exclusions"]["conditions"])

    # -- required documents -----------------------------------------------

    def required_documents(self, category: ClaimCategory) -> list[DocumentType]:
        reqs = self._d["document_requirements"].get(category.value, {}).get("required", [])
        return [DocumentType(r) for r in reqs]

    # -- fraud thresholds -------------------------------------------------

    @property
    def same_day_claims_limit(self) -> int:
        return int(self._d["fraud_thresholds"]["same_day_claims_limit"])

    @property
    def monthly_claims_limit(self) -> int:
        return int(self._d["fraud_thresholds"]["monthly_claims_limit"])

    @property
    def high_value_threshold(self) -> float:
        return float(self._d["fraud_thresholds"]["high_value_claim_threshold"])


def load_policy() -> Policy:
    return Policy()
