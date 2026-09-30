import json

import pandas as pd
import pytest

from cli.utils import load_json, save_json
from core.configuration_errors import ConfigurationFileError
from core.input_columns import choose_input_columns
from core.profile_config import DEFAULTS
from engine.stock_processing.data_processor import remove_unidentified_stock, validate_stock_network
from engine.stock_processing.contracts import StockProcessingPlan
from engine.stock_processing.pricing import process_pricing
from core.configuration_manager import ConfigurationManager
from core import paths as app_paths
from tools.BuildDistribution import distribution_files, ROOT


def test_editor_keeps_existing_corrupt_or_future_configuration(tmp_path):
    path = tmp_path / "configs" / "general" / "catalog.json"
    path.parent.mkdir(parents=True)
    for original in ('{broken', json.dumps({"version": 99, "columns": {"article": "SKU"}})):
        path.write_text(original, encoding="utf-8")
        with pytest.raises(ConfigurationFileError):
            load_json(str(path))
        assert path.read_text(encoding="utf-8") == original
        with pytest.raises(ConfigurationFileError):
            save_json(str(path), DEFAULTS["general/catalog"])
        assert path.read_text(encoding="utf-8") == original


def test_missing_column_requires_explicit_default_choice(tmp_path):
    file = tmp_path / "prices.xlsx"
    pd.DataFrame({"Default SKU": ["A"]}).to_excel(file, index=False)
    with pytest.raises(ValueError, match="configured column"):
        choose_input_columns(str(file), {"article": "SKU"}, {"article": "Default SKU"})
    assert choose_input_columns(
        str(file), {"article": "SKU"}, {"article": "Default SKU"},
        lambda field, wanted, default: True,
    ) == {"article": "Default SKU"}
    with pytest.raises(ValueError, match="both absent"):
        choose_input_columns(str(file), {"article": "SKU"}, {"article": "Absent column"}, lambda *_: True)


def test_unreadable_price_list_fails_instead_of_producing_zero_valuation(tmp_path):
    file = tmp_path / "prices.xlsx"
    pd.DataFrame({"SKU": ["A"], "DB": ["STORE"], "Amount": ["invalid"]}).to_excel(file, index=False)
    config = {"columns": {"article": "SKU", "database": "DB", "price": "Amount"}}
    with pytest.raises(ValueError, match="Could not process required price list"):
        process_pricing(str(file), config)


@pytest.fixture
def stock_plan(tmp_path, monkeypatch):
    monkeypatch.setattr(app_paths, "PROFILES_ROOT", tmp_path / "profiles")
    config = ConfigurationManager("synthetic")
    path = config.base_dir / "general" / "network.json"
    network = json.loads(path.read_text(encoding="utf-8"))
    network["active"] = ["Store A", "Store B"]
    path.write_text(json.dumps(network), encoding="utf-8")
    config.reload()
    return StockProcessingPlan.from_manager(config)


def test_unidentified_stock_is_excluded_with_original_row_and_amount(stock_plan):
    plan = stock_plan
    frame = pd.DataFrame({plan.article_column: ["A", None, ""], "Store A": [1, 4, 0]})
    cleaned, warning = remove_unidentified_stock(frame, plan)
    assert cleaned[plan.article_column].tolist() == ["A"]
    assert "row" in warning and "3 (4 units)" in warning


def test_missing_network_column_fails_before_valuation(stock_plan):
    plan = stock_plan
    frame = pd.DataFrame({plan.article_column: ["A"], "Store A": [4]})
    with pytest.raises(ValueError, match="missing stores"):
        validate_stock_network(frame, plan)


def test_distribution_allowlist_keeps_release_inputs_without_personal_workbooks():
    names = {path.relative_to(ROOT).as_posix() for path in distribution_files()}
    assert "examples/demo/cross_check_system_stock.xls" in names
    assert "tests/release_reference/workbooks/stock_processing.xlsx" in names
    assert "core/input_columns.py" in names
    assert all(name.startswith(("examples/demo/", "tests/")) for name in names if name.endswith((".xls", ".xlsx")))
