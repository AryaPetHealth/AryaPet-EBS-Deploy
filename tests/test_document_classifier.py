from app.services.document_classifier import (
    build_document_card,
    build_lab_report_card,
    build_unknown_card,
    build_vet_visit_card,
    classify_document,
)

_LAB_TEXT = (
    "Specimen collected on March 1, 2026. Reference range noted below. "
    "WBC test result was 7.2 within panel."
)

_VET_TEXT = (
    "Seen at Bayfront Vet Clinic on March 14, 2026. "
    "Diagnosis: mild soft tissue strain. "
    "Treatment plan: rest for two weeks and anti-inflammatory medication."
)


def test_classify_document_detects_lab_report():
    assert classify_document(_LAB_TEXT) == "lab_report"


def test_classify_document_detects_vet_visit():
    assert classify_document(_VET_TEXT) == "vet_visit"


def test_classify_document_matches_lemmatized_keywords():
    # "diagnosed" should match the same as "diagnosis" via lemmatization.
    text = "The vet diagnosed a mild ear infection during the visit."
    assert classify_document(text) == "vet_visit"


def test_classify_document_falls_back_to_unknown():
    assert classify_document("Just a random note with no medical content.") == "unknown"


def test_classify_document_returns_unknown_for_empty_text():
    assert classify_document("   ") == "unknown"


def test_build_lab_report_card_extracts_date_and_result_sentence():
    card = build_lab_report_card(_LAB_TEXT)

    assert card["type"] == "lab_report"
    assert card["collection_date"] == "March 1, 2026"
    assert "WBC test result was 7.2" in card["test_result"]


def test_build_vet_visit_card_extracts_fields():
    card = build_vet_visit_card(_VET_TEXT)

    assert card["type"] == "vet_visit"
    assert card["visit_date"] == "March 14, 2026"
    assert card["clinic_name"] == "Bayfront Vet Clinic"
    assert card["diagnosis"] == "Diagnosis: mild soft tissue strain."
    assert "Treatment plan" in card["treatment_plan"]


def test_build_vet_visit_card_leaves_missing_fields_none():
    card = build_vet_visit_card("Nothing structured here, just a friendly note.")

    assert card["diagnosis"] is None
    assert card["treatment_plan"] is None


def test_build_unknown_card_keeps_raw_text():
    assert build_unknown_card("nothing medical here") == {
        "type": "unknown",
        "raw_text": "nothing medical here",
    }


def test_build_document_card_dispatches_on_classification():
    card = build_document_card(_LAB_TEXT)
    assert card["type"] == "lab_report"

    card2 = build_document_card(_VET_TEXT)
    assert card2["type"] == "vet_visit"

    card3 = build_document_card("Just a random note with no medical content.")
    assert card3["type"] == "unknown"
