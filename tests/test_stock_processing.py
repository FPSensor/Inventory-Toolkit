import pytest
import pandas as pd
from engine.shared.families import assign_families, assign_family, build_family_rules
from engine.stock_processing.data_processor import calculate_margin

def test_classify_family():
    families = {
        "Accesorios": ["30", "40"],
        "Jeans": ["13", "23"]
    }
    rules = build_family_rules(families)
    assert assign_family("30-ABC", rules) == "Accesorios"
    assert assign_family("23-XYZ", rules) == "Jeans"
    assert assign_family("99-ZZZ", rules) == "Other"
    assert assign_family("99-ZZZ", rules, default_family="Otro") == "Otro"

def test_calculate_margin():
    df = pd.DataFrame({
        "Venta": [1000, 2000, 0],
        "Costo": [500, 1500, 500]
    })
    # (Sales value - Cost) / Sales value
    margins = calculate_margin(df, "Venta", "Costo")
    assert margins[0] == 0.50  # 500 / 1000
    assert margins[1] == 0.25  # 500 / 2000
    assert margins[2] == 0.00  # Evita división por cero


def test_batch_family_classifier_matches_iterative_semantics():
    families = {
        "Generic": ["00", "AB"],
        "Specific": ["0085", "ABC"],
        "Duplicate Later": ["AB"],
    }
    rules = build_family_rules(families)
    raw = pd.Series([
        "0085-123",
        "001-XYZ",
        "ABC-1",
        "AB-2",
        "REVISAR | UNKNOWN",
        " 0085-999 ",
        12345,
        None,
    ])

    iterative = raw.apply(
        lambda code: assign_family(code, rules, default_family="Sin clasificar")
    )
    batched = assign_families(raw, rules, default_family="Sin clasificar")

    assert batched.equals(iterative)
    # Duplicate equal prefixes keep stable first-rule priority.
    assert batched.iloc[3] == "Generic"
    # Numeric/None inputs and unmatched values share the configured fallback.
    assert batched.iloc[6] == "Sin clasificar"
    assert batched.iloc[7] == "Sin clasificar"
