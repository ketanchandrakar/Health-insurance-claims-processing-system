"""Gate 2 — cross-document consistency.

Contract:
  check_consistency(docs: list[ExtractedDoc]) -> ConsistencyResult
Fuzzy-matches patient names across documents using partial_ratio so that
"Rajesh Kumar" vs "Rajesh K." passes (score ≥ 85) while clearly different
names like "Rajesh Kumar" vs "Arjun Mehta" fail. On mismatch, the message
names BOTH patients (TC003). Failure STOPS the pipeline.
"""
from thefuzz import fuzz

from app.models import ConsistencyResult, ExtractedDoc

_NAME_MATCH_THRESHOLD = 85


def check_consistency(docs: list[ExtractedDoc]) -> ConsistencyResult:
    named = [d for d in docs if d.patient_name]

    # Need at least two named docs to compare; a single doc is trivially consistent
    if len(named) < 2:
        return ConsistencyResult(consistent=True)

    mismatches: list[dict] = []
    names = [d.patient_name for d in named]

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            score = fuzz.partial_ratio(a.lower(), b.lower())
            if score < _NAME_MATCH_THRESHOLD:
                mismatches.append({
                    "field": "patient_name",
                    "values": [a, b],
                })

    if mismatches:
        # Deduplicate while preserving order for the member-facing message
        seen: dict[str, None] = {}
        for m in mismatches:
            for name in m["values"]:
                seen[name] = None
        all_names = " and ".join(f'"{n}"' for n in seen)
        return ConsistencyResult(
            consistent=False,
            mismatches=mismatches,
            message=(
                f"Documents belong to different patients: {all_names}. "
                f"Please check your uploads and resubmit with documents for the same patient."
            ),
        )

    return ConsistencyResult(consistent=True)
