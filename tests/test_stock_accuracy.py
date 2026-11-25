"""Regressions for Stock Processing inputs that used to lose value silently."""

import json
from argparse import Namespace

import pandas as pd

from core.runtime import paths as app_paths
from engine.stock_processing.generator import run_stock_processing


def _run_stock(tmp_path, monkeypatch, stock, warnings):
    monkeypatch.setattr(app_paths, "PROFILES_ROOT", tmp_path / "profiles")
    configs = tmp_path / "profiles" / "accuracy" / "configs" / "general"
    configs.mkdir(parents=True)
    (configs / "network.json").write_text(json.dumps({
        "version": 3, "active": ["STORE"], "regional_groups": {}, "stock_database_columns": {},
    }), encoding="utf-8")
    settings = configs.parent / "stock_processing" / "settings.json"
    settings.parent.mkdir()
    settings.write_text(json.dumps({
        "version": 3,
        "cleaning": {"text_columns": [], "drop_columns": [], "numeric_columns": ["STORE"]},
        "pricing": {
            "columns": {"article": "Artículo", "database": "Base", "price": "Precio"},
            "aliases": {}, "article_tokenization": "first_token",
        },
        "output": {"raw_data_sheet": "Datos", "base_columns": ["Artículo", "Familias"], "summaries": []},
    }), encoding="utf-8")
    raw, price = tmp_path / "raw.xlsx", tmp_path / "price.xlsx"
    pd.DataFrame(stock, columns=["Artículo", "STORE"]).to_excel(raw, index=False)
    pd.DataFrame({"Artículo": [12345, 12346], "Base": ["STORE"] * 2, "Precio": [100.0, 50.0]}).to_excel(price, index=False)
    result = run_stock_processing(Namespace(
        stock_processing_raw=str(raw), shared_cost=str(price), shared_sales=str(price),
        stock_processing_out=str(tmp_path / "out.xlsx"), stock_processing_profile="accuracy",
        non_interactive=True, warnings=warnings,
    ))
    frame = pd.read_excel(result, sheet_name="Datos", dtype={"Artículo": str})
    return frame.set_index("Artículo")


def test_numeric_articles_are_valued_when_the_column_has_blanks(tmp_path, monkeypatch):
    result = _run_stock(tmp_path, monkeypatch, [(12345, 2), (12346, 1), (None, 0)], [])
    assert result["STORE.Costo"].to_dict() == {"12345": 200, "12346": 50}


def test_stock_reports_missing_prices_and_unclear_quantities(tmp_path, monkeypatch):
    warnings = []
    _run_stock(tmp_path, monkeypatch, [(12345, "1.234"), (99999, 3), (12346, "abc")], warnings)
    text = "\n".join(warnings)
    assert "2 quantities" in text and "STORE" in text
    assert "1 products with stock have no cost price" in text


def test_each_variant_takes_its_own_price(tmp_path, monkeypatch):
    monkeypatch.setattr(app_paths, "PROFILES_ROOT", tmp_path / "profiles")
    configs = tmp_path / "profiles" / "variants" / "configs"
    (configs / "general").mkdir(parents=True)
    (configs / "general" / "network.json").write_text(json.dumps({
        "version": 3, "active": ["STORE"], "regional_groups": {}, "stock_database_columns": {},
    }), encoding="utf-8")
    (configs / "stock_processing").mkdir()
    (configs / "stock_processing" / "settings.json").write_text(json.dumps({
        "version": 3,
        "cleaning": {"text_columns": ["Color", "Talle"], "drop_columns": [], "numeric_columns": ["STORE"]},
        "pricing": {
            "columns": {"article": "Artículo", "database": "Base", "price": "Precio"},
            "aliases": {}, "article_tokenization": "first_token",
            "variant_columns": {"Color": "Color", "Talle": "Talle"},
        },
        "output": {"raw_data_sheet": "Datos", "base_columns": ["Artículo", "Color", "Talle", "Familias"], "summaries": []},
    }), encoding="utf-8")
    raw, price = tmp_path / "raw.xlsx", tmp_path / "price.xlsx"
    pd.DataFrame({
        "Artículo": ["AA-1"] * 3, "Color": ["00", "00", "B2"], "Talle": ["40", "XXXL", "40"], "STORE": [1, 1, 1],
    }).to_excel(raw, index=False)
    pd.DataFrame({
        "Artículo": ["AA-1 TEE"] * 3, "Color": [None, "00 BLACK", "00 BLACK"], "Talle": [None, "40 40", "XXXL XXXL"],
        "Base": ["STORE"] * 3, "Precio": [100.0, 100.0, 250.0],
    }).to_excel(price, index=False)
    warnings = []
    result = run_stock_processing(Namespace(
        stock_processing_raw=str(raw), shared_cost=str(price), shared_sales=str(price),
        stock_processing_out=str(tmp_path / "out.xlsx"), stock_processing_profile="variants", warnings=warnings,
    ))
    frame = pd.read_excel(result, sheet_name="Datos", dtype={"Color": str, "Talle": str})
    # XXXL has its own price; B2 has none, so the product's own row applies, not
    # the average of its variants.
    assert frame["STORE.Costo"].tolist() == [100, 250, 100]
    assert any("1 stock rows have no cost price for their variant" in message for message in warnings)
