"""Gate 2 — cross-document consistency.

Contract:
  check_consistency(docs: list[ExtractedDoc], claim_date: date | None) -> ConsistencyResult

Checks performed in order:
  1. Patient name — fuzzy-match across all named docs (partial_ratio >= 85).
     Scores 85–94 PASS but generate a warning (borderline). Scores < 85 FAIL.
     On hard mismatch the message names BOTH patients (TC003).
  2. Treatment date — cross-doc: all dated docs must agree within DATE_TOLERANCE days.
     Claim vs doc: the claim's stated treatment_date must match each document
     within DATE_TOLERANCE days. Catches the common error where the date
     typed in the submission form does not match the date on the bill/prescription.
     Dates that differ by 1–DATE_TOLERANCE days PASS but generate a warning.

Hard mismatches → consistent=False, pipeline STOPS.
Borderline passes → consistent=True, warnings populated, synthesizer applies -0.10 penalty.
"""
from __future__ import annotations

from datetime import date
from thefuzz import fuzz

from app.models import ConsistencyResult, ExtractedDoc

_NAME_MATCH_THRESHOLD = 85
_NAME_WARNING_CEILING = 95   # score in [85, 95) → pass with warning
_DATE_TOLERANCE_DAYS = 3


def check_consistency(
    docs: list[ExtractedDoc],
    claim_date: date | None = None,
) -> ConsistencyResult:
    mismatches: list[dict] = []
    warnings: list[str] = []

    # ------------------------------------------------------------------
    # 1. Patient name cross-check
    # ------------------------------------------------------------------
    named = [d for d in docs if d.patient_name]
    if len(named) >= 2:
        names = [d.patient_name for d in named]
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = names[i], names[j]
                score = fuzz.partial_ratio(a.lower(), b.lower())
                if score < _NAME_MATCH_THRESHOLD:
                    mismatches.append({"field": "patient_name", "values": [a, b]})
                elif score < _NAME_WARNING_CEILING:
                    warnings.append(
                        f"Patient name near-match ({score}%): \"{a}\" vs \"{b}\" — "
                        f"verify these are the same person."
                    )

    # ------------------------------------------------------------------
    # 2. Treatment date checks
    # ------------------------------------------------------------------
    dated = [d for d in docs if d.treatment_date is not None]

    # 2a. Cross-doc: all documents must agree on the treatment date
    if len(dated) >= 2:
        for i in range(len(dated)):
            for j in range(i + 1, len(dated)):
                a_date = dated[i].treatment_date
                b_date = dated[j].treatment_date
                gap = abs((a_date - b_date).days)
                if gap > _DATE_TOLERANCE_DAYS:
                    mismatches.append({
                        "field": "treatment_date",
                        "values": [a_date.isoformat(), b_date.isoformat()],
                        "source": ["document", "document"],
                    })
                elif gap > 0:
                    warnings.append(
                        f"Minor date discrepancy across documents: "
                        f"{a_date.isoformat()} vs {b_date.isoformat()} ({gap} day(s))."
                    )

    # 2b. Claim vs doc: claimed treatment_date must match what documents show
    if claim_date is not None and dated:
        for doc in dated:
            gap = abs((doc.treatment_date - claim_date).days)
            if gap > _DATE_TOLERANCE_DAYS:
                mismatches.append({
                    "field": "treatment_date",
                    "values": [claim_date.isoformat(), doc.treatment_date.isoformat()],
                    "source": ["claim", "document"],
                })
                break  # one report is enough — member needs to fix the date
            elif gap > 0:
                warnings.append(
                    f"Claimed treatment date ({claim_date.isoformat()}) differs slightly "
                    f"from document date ({doc.treatment_date.isoformat()}) by {gap} day(s)."
                )
                break

    if mismatches:
        # ------------------------------------------------------------------
        # Build a specific, actionable member-facing message
        # ------------------------------------------------------------------
        parts: list[str] = []

        name_mm = [m for m in mismatches if m["field"] == "patient_name"]
        date_mm = [m for m in mismatches if m["field"] == "treatment_date"]

        if name_mm:
            seen: dict[str, None] = {}
            for m in name_mm:
                for name in m["values"]:
                    seen[name] = None
            all_names = " and ".join(f'"{n}"' for n in seen)
            parts.append(f"Documents belong to different patients: {all_names}.")

        for m in date_mm:
            claimed_date, doc_date = m["values"]
            src = m.get("source", ["document", "document"])
            if src[0] == "claim":
                parts.append(
                    f"Claimed treatment date ({claimed_date}) does not match "
                    f"the date on your document ({doc_date})."
                )
            else:
                parts.append(
                    f"Documents show conflicting treatment dates: "
                    f"{claimed_date} vs {doc_date}."
                )

        message = " ".join(parts) + " Please check your uploads and resubmit."

        return ConsistencyResult(
            consistent=False,
            mismatches=mismatches,
            warnings=warnings,
            message=message,
        )

    return ConsistencyResult(consistent=True, warnings=warnings)
