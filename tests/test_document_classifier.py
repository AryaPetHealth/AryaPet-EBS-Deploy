from app.services.document_classifier import (
    build_document_card,
    classify_document,
    extract_text_and_tables,
)


def _line_block(block_id: str, text: str) -> dict:
    return {"Id": block_id, "BlockType": "LINE", "Text": text}


def _word_block(block_id: str, text: str) -> dict:
    return {"Id": block_id, "BlockType": "WORD", "Text": text}


def _cell_block(block_id: str, row: int, col: int, word_ids: list[str]) -> dict:
    return {
        "Id": block_id,
        "BlockType": "CELL",
        "RowIndex": row,
        "ColumnIndex": col,
        "Relationships": [{"Type": "CHILD", "Ids": word_ids}],
    }


def _table_response(lines: list[str], rows: list[list[str]]) -> dict:
    blocks = [_line_block(f"line-{i}", text) for i, text in enumerate(lines)]

    cell_ids = []
    word_counter = 0
    for r, row in enumerate(rows, start=1):
        for c, cell_text in enumerate(row, start=1):
            word_id = f"word-{word_counter}"
            word_counter += 1
            blocks.append(_word_block(word_id, cell_text))
            cell_id = f"cell-{r}-{c}"
            cell_ids.append(cell_id)
            blocks.append(_cell_block(cell_id, r, c, [word_id]))

    blocks.append(
        {"Id": "table-1", "BlockType": "TABLE", "Relationships": [{"Type": "CHILD", "Ids": cell_ids}]}
    )
    return {"Blocks": blocks}


def test_extract_text_and_tables_reads_lines_and_table_cells():
    response = _table_response(
        lines=["Specimen: Blood", "Reference Range noted below"],
        rows=[["Test", "Result", "Units", "Reference Range"], ["WBC", "7.2", "10^9/L", "6.0-17.0"]],
    )

    text, tables = extract_text_and_tables(response)

    assert "Specimen: Blood" in text
    assert len(tables) == 1
    assert tables[0][1] == ["WBC", "7.2", "10^9/L", "6.0-17.0"]


def test_classify_document_detects_lab_report_from_table_and_keywords():
    response = _table_response(
        lines=["Specimen: Blood", "Reference Range noted below"],
        rows=[["Test", "Result", "Units", "Reference Range"], ["WBC", "7.2", "10^9/L", "6.0-17.0"]],
    )
    text, tables = extract_text_and_tables(response)

    assert classify_document(text, tables) == "lab_report"


def test_classify_document_detects_vet_visit_from_keywords_without_tables():
    text = (
        "Presenting complaint: limping on left hind leg.\n"
        "Diagnosis: mild soft tissue strain.\n"
        "Treatment plan: rest for two weeks and anti-inflammatory medication.\n"
        "Seen at Bayfront Vet Clinic on 03/14/2026 by Dr. Smith."
    )

    assert classify_document(text, []) == "vet_visit"


def test_classify_document_falls_back_to_unknown():
    assert classify_document("Just a random note with no medical content.", []) == "unknown"


def test_build_document_card_for_lab_report():
    response = _table_response(
        lines=["Specimen collected 2026-03-01", "Reference Range noted below"],
        rows=[["Test", "Result", "Units", "Reference Range"], ["WBC", "7.2", "10^9/L", "6.0-17.0"]],
    )
    text, tables = extract_text_and_tables(response)

    card = build_document_card(text, tables)

    assert card["type"] == "lab_report"
    assert card["collection_date"] == "2026-03-01"
    assert card["test_results"] == [
        {"name": "WBC", "value": "7.2", "unit": "10^9/L", "reference_range": "6.0-17.0"}
    ]


def test_build_document_card_for_vet_visit():
    text = (
        "Visit date: March 14, 2026\n"
        "Diagnosis: mild soft tissue strain\n"
        "Treatment plan: rest for two weeks and anti-inflammatory medication\n"
        "Seen at Bayfront Vet Clinic."
    )

    card = build_document_card(text, [])

    assert card["type"] == "vet_visit"
    assert card["diagnosis"] == "mild soft tissue strain"
    assert card["treatment_plan"] == "rest for two weeks and anti-inflammatory medication"


def test_build_document_card_for_unknown_keeps_raw_text():
    text = "Nothing medical here."

    card = build_document_card(text, [])

    assert card == {"type": "unknown", "raw_text": text}
