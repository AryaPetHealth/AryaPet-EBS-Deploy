from unittest.mock import patch

from app.services.document_classifier import (
    build_document_card,
    build_lab_report_card,
    build_unknown_card,
    build_vet_visit_card,
    classify_document,
)


def _fake_classification(labels_and_scores: dict[str, float]):
    ordered = sorted(labels_and_scores.items(), key=lambda item: item[1], reverse=True)

    def _pipeline(text: str, candidate_labels: list[str]):
        return {"labels": [label for label, _ in ordered], "scores": [score for _, score in ordered]}

    return _pipeline


def _fake_qa(answers: dict[str, tuple[str, float]]):
    def _pipeline(question: str, context: str):
        answer, score = answers.get(question, ("", 0.0))
        return {"answer": answer, "score": score}

    return _pipeline


def test_classify_document_returns_lab_report_above_threshold():
    fake = _fake_classification({"lab report": 0.9, "veterinary visit note": 0.1})
    with patch("app.services.document_classifier._classification_pipeline", return_value=fake):
        assert classify_document("some report text") == "lab_report"


def test_classify_document_returns_vet_visit_above_threshold():
    fake = _fake_classification({"lab report": 0.2, "veterinary visit note": 0.8})
    with patch("app.services.document_classifier._classification_pipeline", return_value=fake):
        assert classify_document("some visit text") == "vet_visit"


def test_classify_document_returns_unknown_below_confidence_threshold():
    fake = _fake_classification({"lab report": 0.4, "veterinary visit note": 0.35})
    with patch("app.services.document_classifier._classification_pipeline", return_value=fake):
        assert classify_document("ambiguous text") == "unknown"


def test_classify_document_returns_unknown_for_empty_text():
    assert classify_document("   ") == "unknown"


def test_build_lab_report_card_uses_qa_answers_above_threshold():
    fake = _fake_qa(
        {
            "What is the collection date?": ("2026-03-01", 0.8),
            "What test was performed?": ("WBC", 0.7),
            "What is the result value?": ("7.2", 0.6),
        }
    )
    with patch("app.services.document_classifier._qa_pipeline", return_value=fake):
        card = build_lab_report_card("some report text")

    assert card == {
        "type": "lab_report",
        "collection_date": "2026-03-01",
        "test_name": "WBC",
        "result_value": "7.2",
    }


def test_build_vet_visit_card_drops_low_confidence_answers():
    fake = _fake_qa(
        {
            "What is the visit date?": ("March 14, 2026", 0.9),
            "What is the name of the clinic?": ("Bayfront Vet Clinic", 0.85),
            "What is the diagnosis?": ("mild soft tissue strain", 0.75),
            "What is the treatment plan?": ("irrelevant guess", 0.02),
        }
    )
    with patch("app.services.document_classifier._qa_pipeline", return_value=fake):
        card = build_vet_visit_card("some visit text")

    assert card["visit_date"] == "March 14, 2026"
    assert card["clinic_name"] == "Bayfront Vet Clinic"
    assert card["diagnosis"] == "mild soft tissue strain"
    assert card["treatment_plan"] is None


def test_build_unknown_card_keeps_raw_text():
    assert build_unknown_card("nothing medical here") == {
        "type": "unknown",
        "raw_text": "nothing medical here",
    }


def test_build_document_card_dispatches_on_classification():
    classify_fake = _fake_classification({"lab report": 0.9, "veterinary visit note": 0.1})
    qa_fake = _fake_qa({"What is the collection date?": ("2026-03-01", 0.8)})
    with (
        patch("app.services.document_classifier._classification_pipeline", return_value=classify_fake),
        patch("app.services.document_classifier._qa_pipeline", return_value=qa_fake),
    ):
        card = build_document_card("some report text")

    assert card["type"] == "lab_report"
    assert card["collection_date"] == "2026-03-01"
