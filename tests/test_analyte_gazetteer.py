from app.services.analyte_gazetteer import annotate_parameters, canonical_analyte


def test_canonical_analyte_collapses_lab_specific_spellings():
    # The whole point: these are one analyte, and must not become separate trends.
    for spelling in ("ALP", "Alk Phos", "Alkaline Phosphatase", "S. Alkaline Phosphatase"):
        assert canonical_analyte(spelling) == "Alkaline Phosphatase"


def test_canonical_analyte_ignores_case_and_punctuation():
    assert canonical_analyte("alt (sgpt)") == "Alanine Aminotransferase"
    assert canonical_analyte("ALT (SGPT)") == "Alanine Aminotransferase"
    assert canonical_analyte("  SGPT  ") == "Alanine Aminotransferase"


def test_canonical_analyte_distinguishes_similar_bilirubins():
    assert canonical_analyte("Direct bilirubin") == "Direct Bilirubin"
    assert canonical_analyte("Indirect bilirubin") == "Indirect Bilirubin"
    assert canonical_analyte("Total Bilirubin") == "Total Bilirubin"


def test_canonical_analyte_returns_none_for_unknown_and_empty():
    assert canonical_analyte("Wibble Factor") is None
    assert canonical_analyte("") is None
    assert canonical_analyte("   ") is None


def test_annotate_parameters_adds_canonical_name_without_losing_the_original():
    params = [
        {"name": "ALP", "value": "1071.4"},
        {"name": "BUN", "value": "33.6"},
    ]
    annotate_parameters(params)

    assert params[0]["name"] == "ALP"
    assert params[0]["canonical_name"] == "Alkaline Phosphatase"
    assert params[1]["canonical_name"] == "Blood Urea Nitrogen"


def test_annotate_parameters_leaves_unknown_analytes_untouched():
    # An unmapped result is still a result - it must not be dropped or renamed.
    params = [{"name": "Wibble Factor", "value": "42"}]
    annotate_parameters(params)

    assert params[0]["name"] == "Wibble Factor"
    assert "canonical_name" not in params[0]
