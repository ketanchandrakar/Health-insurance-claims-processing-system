"""Tests for agents.consistency — Gate 2 cross-document consistency."""
from datetime import date

from app.agents.consistency import check_consistency
from app.models import DocumentType, ExtractedDoc, ExtractedDocStatus


def _doc(
    file_id: str,
    patient_name: str | None = None,
    treatment_date: date | None = None,
) -> ExtractedDoc:
    return ExtractedDoc(
        file_id=file_id,
        doc_type=DocumentType.HOSPITAL_BILL,
        patient_name=patient_name,
        treatment_date=treatment_date,
        doc_confidence=0.95,
        status=ExtractedDocStatus.OK,
    )


# ---------------------------------------------------------------------------
# Patient name checks (original TC003 coverage)
# ---------------------------------------------------------------------------

def test_tc003_patient_mismatch():
    docs = [_doc("F005", "Rajesh Kumar"), _doc("F006", "Arjun Mehta")]
    result = check_consistency(docs)

    assert result.consistent is False
    assert result.message is not None
    assert "Rajesh Kumar" in result.message
    assert "Arjun Mehta" in result.message
    assert len(result.mismatches) > 0


def test_same_patient_consistent():
    docs = [_doc("F007", "Rajesh Kumar"), _doc("F008", "Rajesh Kumar")]
    result = check_consistency(docs)
    assert result.consistent is True
    assert result.mismatches == []


def test_fuzzy_match_passes():
    docs = [_doc("F001", "Rajesh Kumar"), _doc("F002", "Rajesh K.")]
    result = check_consistency(docs)
    assert result.consistent is True


def test_single_named_doc_skips_check():
    docs = [_doc("F001", "Rajesh Kumar"), _doc("F002", None)]
    result = check_consistency(docs)
    assert result.consistent is True


# ---------------------------------------------------------------------------
# Treatment date — claim vs document
# ---------------------------------------------------------------------------

def test_claim_date_matches_doc_date():
    d = date(2024, 11, 1)
    docs = [_doc("F001", treatment_date=d)]
    result = check_consistency(docs, claim_date=d)
    assert result.consistent is True


def test_claim_date_within_tolerance_passes():
    # 2-day gap is within the 3-day tolerance
    docs = [_doc("F001", treatment_date=date(2024, 11, 3))]
    result = check_consistency(docs, claim_date=date(2024, 11, 1))
    assert result.consistent is True


def test_claim_date_mismatch_stops_pipeline():
    # User typed Jan 1 but the bill says Nov 1 — clear mismatch
    docs = [_doc("F001", treatment_date=date(2024, 11, 1))]
    result = check_consistency(docs, claim_date=date(2024, 1, 1))

    assert result.consistent is False
    assert result.message is not None
    assert "2024-01-01" in result.message
    assert "2024-11-01" in result.message
    assert any(m["field"] == "treatment_date" for m in result.mismatches)


def test_claim_date_message_names_both_dates():
    docs = [_doc("F001", treatment_date=date(2024, 6, 15))]
    result = check_consistency(docs, claim_date=date(2024, 3, 10))

    assert "2024-03-10" in result.message
    assert "2024-06-15" in result.message


# ---------------------------------------------------------------------------
# Treatment date — cross-document
# ---------------------------------------------------------------------------

def test_cross_doc_dates_consistent():
    d = date(2024, 11, 1)
    docs = [
        _doc("F001", treatment_date=d),
        _doc("F002", treatment_date=date(2024, 11, 2)),  # 1-day gap, within tolerance
    ]
    result = check_consistency(docs)
    assert result.consistent is True


def test_cross_doc_dates_mismatch():
    docs = [
        _doc("F001", treatment_date=date(2024, 11, 1)),
        _doc("F002", treatment_date=date(2024, 9, 1)),  # 2-month gap
    ]
    result = check_consistency(docs)

    assert result.consistent is False
    assert any(m["field"] == "treatment_date" for m in result.mismatches)
    assert "2024-11-01" in result.message
    assert "2024-09-01" in result.message


def test_no_dated_docs_skips_date_check():
    # Docs have no extracted treatment_date — date check is skipped, passes
    docs = [_doc("F001", patient_name="Rajesh Kumar"), _doc("F002", patient_name="Rajesh Kumar")]
    result = check_consistency(docs, claim_date=date(2024, 11, 1))
    assert result.consistent is True


def test_combined_name_and_date_mismatch():
    docs = [
        _doc("F001", patient_name="Rajesh Kumar", treatment_date=date(2024, 11, 1)),
        _doc("F002", patient_name="Arjun Mehta",  treatment_date=date(2024, 11, 1)),
    ]
    result = check_consistency(docs, claim_date=date(2024, 1, 1))

    assert result.consistent is False
    name_mm = [m for m in result.mismatches if m["field"] == "patient_name"]
    date_mm = [m for m in result.mismatches if m["field"] == "treatment_date"]
    assert len(name_mm) > 0
    assert len(date_mm) > 0


# ---------------------------------------------------------------------------
# Warnings — borderline passes that reduce confidence
# ---------------------------------------------------------------------------

def test_borderline_name_score_generates_warning():
    # "Rajesh K." vs "Rajesh Kumar": score passes (>= 85) but is not a perfect
    # match — should produce a warning without failing consistency.
    docs = [_doc("F001", "Rajesh Kumar"), _doc("F002", "Rajesh K.")]
    result = check_consistency(docs)

    assert result.consistent is True
    assert len(result.warnings) > 0
    assert any("name" in w.lower() or "match" in w.lower() for w in result.warnings)


def test_near_miss_date_generates_warning():
    # 2-day gap is within tolerance but non-zero → warning
    docs = [_doc("F001", treatment_date=date(2024, 11, 1))]
    result = check_consistency(docs, claim_date=date(2024, 11, 3))

    assert result.consistent is True
    assert len(result.warnings) > 0
    assert any("2024-11-01" in w or "2024-11-03" in w for w in result.warnings)


def test_exact_match_no_warnings():
    d = date(2024, 11, 1)
    docs = [_doc("F001", patient_name="Rajesh Kumar", treatment_date=d),
            _doc("F002", patient_name="Rajesh Kumar", treatment_date=d)]
    result = check_consistency(docs, claim_date=d)

    assert result.consistent is True
    assert result.warnings == []
