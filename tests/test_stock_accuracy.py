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


def test_negative_stock_without_price_counts_its_units(tmp_path, monkeypatch):
    warnings = []
    _run_stock(tmp_path, monkeypatch, [(12345, 1), (99998, -1), (99999, 1)], warnings)
    assert "so 2 units are valued at 0" in "\n".join(warnings)


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


def test_stock_without_cost_is_listed_in_its_own_workbook(tmp_path, monkeypatch):
    monkeypatch.setattr(app_paths, "PROFILES_ROOT", tmp_path / "profiles")
    configs = tmp_path / "profiles" / "listing" / "configs"
    (configs / "general").mkdir(parents=True)
    (configs / "general" / "network.json").write_text(json.dumps({
        "version": 3, "active": ["NORTH", "SOUTH"], "regional_groups": {}, "stock_database_columns": {},
    }), encoding="utf-8")
    (configs / "stock_processing").mkdir()
    settings = {
        "version": 3,
        "cleaning": {"text_columns": [], "drop_columns": [], "numeric_columns": []},
        "pricing": {"columns": {"article": "Artículo", "database": "Base", "price": "Precio"}},
        "output": {"raw_data_sheet": "Datos", "base_columns": ["Artículo", "Familias"], "summaries": [],
                   "missing_cost_file": "Sin costo"},
    }
    (configs / "stock_processing" / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
    raw, cost, sales = (tmp_path / name for name in ("raw.xlsx", "cost.xlsx", "sales.xlsx"))
    pd.DataFrame({"Artículo": ["AA-1", "BB-2", "CC-3"], "NORTH": [3, 0, 1], "SOUTH": [2, 4, 0]}).to_excel(raw, index=False)
    # AA-1 lacks cost in NORTH only; BB-2 lacks it everywhere but has stock only in SOUTH; CC-3 has cost.
    pd.DataFrame({"Artículo": ["AA-1", "CC-3"], "Base": ["SOUTH", "NORTH"], "Precio": [10.0, 10.0]}).to_excel(cost, index=False)
    pd.DataFrame({"Artículo": ["AA-1", "AA-1", "BB-2", "CC-3"], "Base": ["NORTH", "SOUTH", "SOUTH", "NORTH"],
                  "Precio": [50.0, 50.0, 20.0, 30.0]}).to_excel(sales, index=False)
    warnings = []
    report = run_stock_processing(Namespace(
        stock_processing_raw=str(raw), shared_cost=str(cost), shared_sales=str(sales),
        stock_processing_out=str(tmp_path / "Stock.xlsx"), stock_processing_profile="listing", warnings=warnings,
    ))
    listing = pd.read_excel(tmp_path / "Stock - Sin costo.xlsx")
    assert listing["Artículo"].tolist() == ["AA-1", "BB-2"]
    assert listing["NORTH"].fillna(0).tolist() == [3, 0]
    assert listing["SOUTH"].fillna(0).tolist() == [0, 4]
    assert listing["NORTH.Venta"].fillna(0).tolist() == [150, 0]
    assert any("2 products with stock have no cost" in message for message in warnings)
    assert not any("no cost price in at least one store" in message for message in warnings)
    assert pd.read_excel(report, sheet_name="Datos")["NORTH.Costo"].tolist() == [0, 0, 10]


def test_price_lists_only_read_active_stores(tmp_path):
    from engine.stock_processing.pricing import process_pricing

    path = tmp_path / "prices.xlsx"
    pd.DataFrame({
        "Artículo": ["A1", "A1", "A1", "A2"],
        "Base": ["STORE", "CLOSED", "CLOSED", "CLOSED"],
        "Precio": [100, 10, 20, "abc"],
    }).to_excel(path, index=False)
    notices = []
    config = {"columns": {"article": "Artículo", "database": "Base", "price": "Precio"}}
    prices = process_pricing(str(path), config, notices.append, stores=["STORE"])
    assert prices.set_index("__itk_article")["STORE"].to_dict() == {"A1": 100}
    assert "CLOSED" not in prices.columns
    assert not [notice for notice in notices if notice and "more than one price" in notice]
