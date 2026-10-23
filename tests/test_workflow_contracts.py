from types import SimpleNamespace
import pandas as pd
import pytest

from core.workflow_contracts import stock_input
from engine.stock_processing.data_processor import adapt_stock_headers


def test_explicit_stock_headers_are_independent_from_output_and_locations():
    source = {"article_column": "Product code", "quantity_columns": {"Front": "On hand"}, "deposit_columns": {}}
    manager = SimpleNamespace(
        get_catalog_columns=lambda: {"article": "SKU"},
        get_network_config=lambda: {"active": ["Different location"], "stock_database_columns": {}},
        get_stock_processing_config=lambda: {"input": source})
    resolved = stock_input(manager)
    assert resolved == source
    plan = SimpleNamespace(article_column="SKU", input=resolved)
    adapted = adapt_stock_headers(pd.DataFrame({"Product code": ["A"], "On hand": [1.25]}), plan, "Product code")
    assert adapted.to_dict("list") == {"SKU": ["A"], "Front": [1.25]}
    with pytest.raises(ValueError, match="missing configured"):
        adapt_stock_headers(pd.DataFrame({"SKU": ["A"], "On hand": [1]}), plan, "Product code")


def test_long_stock_maps_rows_without_assuming_variant_aggregation():
    source = {"format": "long", "quantity_column": "Weight", "branch_column": "Location", "default_store": ""}
    plan = SimpleNamespace(article_column="SKU", active_stores=("Front", "Back"), input=source)
    frame = pd.DataFrame({"Code": ["001", "001"], "Weight": [1.25, 2.5], "Location": ["Front", "Back"]})
    adapted = adapt_stock_headers(frame, plan, "Code")
    assert adapted["SKU"].tolist() == ["001", "001"]
    assert adapted["Front"].sum() == 1.25 and adapted["Back"].sum() == 2.5
    with pytest.raises(ValueError, match="Excel rows"):
        adapt_stock_headers(frame.assign(Location="Unknown"), plan, "Code")


def test_single_location_prices_preserve_codes_and_apply_origin_aliases(tmp_path):
    from engine.stock_processing.pricing import process_pricing
    from engine.stock_processing.contracts import INTERNAL_ARTICLE_COLUMN
    path = tmp_path / "prices.xlsx"
    pd.DataFrame({"Code": ["001"], "Value": [12.5]}).to_excel(path, index=False)
    pricing = {"columns": {"article": "Code", "database": "", "price": "Value"}, "default_store": "Counter"}
    assert process_pricing(path, pricing).to_dict("list") == {INTERNAL_ARTICLE_COLUMN: ["001"], "Counter": [12.5]}
    pd.DataFrame({"Code": ["001"], "Value": [12.5], "Origin": ["Main register"]}).to_excel(path, index=False)
    pricing["columns"]["database"] = "Origin"
    pricing["aliases"] = {"Main register": "Counter"}
    assert process_pricing(path, pricing)["Counter"].iloc[0] == 12.5
