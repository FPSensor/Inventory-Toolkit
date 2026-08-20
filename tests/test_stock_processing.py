import pytest
import pandas as pd
from engine.shared.families import build_family_rules, assign_family
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

def test_calculate_margin():
    df = pd.DataFrame({
        "Venta": [1000, 2000, 0],
        "Costo": [500, 1500, 500]
    })
    # (Venta - Costo) / Venta
    margins = calculate_margin(df, "Venta", "Costo")
    assert margins[0] == 0.50  # 500 / 1000
    assert margins[1] == 0.25  # 500 / 2000
    assert margins[2] == 0.00  # Evita división por cero
