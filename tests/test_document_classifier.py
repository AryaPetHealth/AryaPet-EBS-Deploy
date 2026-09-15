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


# Regression test for a real multi-parameter LFT + KFT report where the
# client-side parser was silently dropping every row after the first one per
# section - the row-clean "name value range unit" layout wasn't recognized
# there, and the same gap existed here: this module only ever captured one
# sentence per lab report, never the full panel.
_LFT_KFT_TEXT = """\
PET ID: Daisy (Canine) PET AGE: 9Y SAMPLE RECEIVED DATE: 21.09.2025 GENDER: Female
PET BREED: Indian
DATE OF TEST RESULT: 21.09.2025
LIVER FUNCTION TEST
Parameter Value Normal range
Albumin 2.5 2.2 – 4.0 g/dl
ALP 1071.4 14-111 U/L
ALT 133.5 10-109 U/L
AST 94.3 10-100 U/L
Direct bilirubin 0.73 0.05-0.1 mg/dl
Indirect bilirubin 0.35 0.01-0.3 mg/dl
Total Bilirubin 1.08 0.1-0.6 mg/dl
Globulin 2.2 2.8-5.1 g/dl
A/G Ratio 1.1 0.7-2.0
Total Protein 4.7 5.7-8.9 g/dl
*****End of Report*****
Dr.B.Sushma
M.V.Sc (Microbiology)
PET ID: Daisy (Canine) PET AGE: 9Y SAMPLE RECEIVED DATE: 21.09.2025 GENDER: Female
PET BREED: Indian
DATE OF TEST RESULT: 21.09.2025
KIDNEY FUNCTION TEST
Parameter Value Normal range
Creatinine 1.5 0.6 – 1.4 mg/dl
Blood Urea 72.0 12.8-53.5 mg/dl
BUN 33.6 8-28 mg/dl
Uric acid 0.3 0-1.0 mg/dl
BUN/Creatinine ratio 22.4 4-27
*****End of Report*****
Dr.B.Sushma
M.V.Sc (Microbiology)
"""


def test_build_lab_report_card_extracts_every_parameter_in_every_section():
    card = build_lab_report_card(_LFT_KFT_TEXT)

    assert card["type"] == "lab_report"
    sections = {s["title"]: s["parameters"] for s in card["sections"]}
    assert list(sections) == ["Liver Function Test", "Kidney Function Test"]

    lft = sections["Liver Function Test"]
    assert [p["name"] for p in lft] == [
        "Albumin",
        "ALP",
        "ALT",
        "AST",
        "Direct bilirubin",
        "Indirect bilirubin",
        "Total Bilirubin",
        "Globulin",
        "A/G Ratio",
        "Total Protein",
    ]
    assert [p["value"] for p in lft] == [
        "2.5", "1071.4", "133.5", "94.3", "0.73", "0.35", "1.08", "2.2", "1.1", "4.7",
    ]
    # ALP is well outside its 14-111 U/L range - confirms the abnormal flag
    # survives the table walk, not just the name/value pairing.
    alp = next(p for p in lft if p["name"] == "ALP")
    assert alp["unit"] == "U/L"
    assert alp["abnormal"] is True

    kft = sections["Kidney Function Test"]
    assert [p["name"] for p in kft] == [
        "Creatinine", "Blood Urea", "BUN", "Uric acid", "BUN/Creatinine ratio",
    ]
    assert [p["value"] for p in kft] == ["1.5", "72.0", "33.6", "0.3", "22.4"]


def test_build_lab_report_card_omits_sections_key_when_no_table_found():
    card = build_lab_report_card(_LAB_TEXT)
    assert "sections" not in card
