"""Tests for agents.consistency — Gate 2 cross-document patient matching."""
from app.agents.consistency import check_consistency
from app.models import DocumentType, ExtractedDoc, ExtractedDocStatus


def _doc(file_id: str, patient_name: str | None) -> ExtractedDoc:
    return ExtractedDoc(
        file_id=file_id,
        doc_type=DocumentType.HOSPITAL_BILL,
        patient_name=patient_name,
        doc_confidence=0.95,
        status=ExtractedDocStatus.OK,
    )


def test_tc003_patient_mismatch():
    # TC003: prescription for Rajesh Kumar, bill for Arjun Mehta
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
    # Abbreviated name should not fail — "Rajesh K." is recognisably "Rajesh Kumar"
    docs = [_doc("F001", "Rajesh Kumar"), _doc("F002", "Rajesh K.")]
    result = check_consistency(docs)
    assert result.consistent is True


def test_single_named_doc_skips_check():
    # Only one doc has a patient name — nothing to compare, must pass
    docs = [_doc("F001", "Rajesh Kumar"), _doc("F002", None)]
    result = check_consistency(docs)
    assert result.consistent is True
