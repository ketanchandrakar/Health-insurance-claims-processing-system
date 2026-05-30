"""Gate 2 — cross-document consistency.

Contract:
  check_consistency(docs: list[ExtractedDoc]) -> ConsistencyResult
Fuzzy-matches patient names across documents (so "Rajesh Kumar" vs
"Rajesh K." does not fail), plus dates and totals. On mismatch, names BOTH
patients in the message (TC003). Failure STOPS the pipeline.
"""
from app.models import ConsistencyResult, ExtractedDoc


def check_consistency(docs: list[ExtractedDoc]) -> ConsistencyResult:
    #yet to implement
    return ConsistencyResult(consistent=True)
