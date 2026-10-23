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
