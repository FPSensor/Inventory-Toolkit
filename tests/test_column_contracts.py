from argparse import Namespace
from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

from core import paths as app_paths
from core.profile_config import DEFAULTS, _write, config_path
from engine.inventory_cross_check.generator import run_cross_check
from engine.stock_processing.generator import run_stock_processing


def _write_profile(root: Path, profile: str, overrides: dict[str, dict]) -> None:
    configs = root / "profiles" / profile / "configs"
    for logical_name, default in DEFAULTS.items():
        payload = deepcopy(default)
        if logical_name in overrides:
            payload = overrides[logical_name]
        _write(config_path(configs, logical_name), payload)


def test_stock_processing_honors_custom_catalog_and_pricing_columns(tmp_path, monkeypatch):
    profile = "custom-stock"
    _write_profile(
        tmp_path,
        profile,
        {
            "general/catalog": {
                "version": 3,
                "columns": {"article": "SKU_TEST", "family": "FAMILY_TEST"},
                "default_family": "UNMAPPED",
            },
            "general/families": {
                "version": 3,
                "rules": {"Family A": ["AA"], "REVISAR": ["REVISAR"]},
            },
            "general/network": {
                "version": 3,
                "active": ["STORE_A"],
                "regional_groups": {"REGION": ["STORE_A"]},
                "stock_database_columns": {"STORE_A": "DEP_A"},
            },
            "stock_processing/settings": {
                "version": 3,
                "cleaning": {
                    "text_columns": ["SKU_TEST", "Color"],
                    "drop_columns": [],
                    "numeric_columns": ["STORE_A", "DEP_A"],
                },
                "pricing": {
                    "columns": {
                        "article": "SKU_PRICE",
                        "database": "DB_TEST",
                        "price": "VALUE_TEST",
                    },
                    "aliases": {},
                },
                "output": {
                    "raw_data_sheet": "RAW",
                    # Keep historical canonical labels here on purpose. The
                    # catalog contract must still expose the configured names.
                    "base_columns": ["Artículo", "Color", "Familias"],
                    "summaries": [
                        {
                            "sheet_name": "Summary",
                            "entities": ["STORE_A"],
                            "titles": [],
                        }
                    ],
                },
            },
        },
    )
    monkeypatch.setattr(app_paths, "PROFILES_ROOT", tmp_path / "profiles")

    stock_path = tmp_path / "stock.xlsx"
    cost_path = tmp_path / "cost.xlsx"
    sales_path = tmp_path / "sales.xlsx"
    output_path = tmp_path / "out.xlsx"

    pd.DataFrame(
        {
            "SKU_TEST": [" AA1 ", "ZZ9", None],
            "Color": [" Red ", "Blue", ""],
            "STORE_A": [2, 1, 7],
            "DEP_A": [3, 0, 0],
        }
    ).to_excel(stock_path, index=False)
    pd.DataFrame(
        {
            "SKU_PRICE": ["AA1 description", "ZZ9"],
            "DB_TEST": ["STORE_A", "STORE_A"],
            "VALUE_TEST": [10, 20],
        }
    ).to_excel(cost_path, index=False)
    pd.DataFrame(
        {
            "SKU_PRICE": ["AA1 description", "ZZ9"],
            "DB_TEST": ["STORE_A", "STORE_A"],
            "VALUE_TEST": [30, 40],
        }
    ).to_excel(sales_path, index=False)

    warnings = []
    events = []
    stats = []
    result = run_stock_processing(
        Namespace(
            stock_processing_raw=str(stock_path),
            shared_cost=str(cost_path),
            shared_sales=str(sales_path),
            stock_processing_out=str(output_path),
            stock_processing_profile=profile,
            non_interactive=True,
            warnings=warnings,
            progress=events.append,
            stats=stats.append,
        )
    )
    assert result == str(output_path)
    assert len(warnings) == 1 and "4 (7 units)" in warnings[0]
    assert [event.completed for event in events] == [0, 1, 2, 3, 4]
    assert "Stock loaded and cleaned" in events[1].message
    assert events[-1].fraction == 1
    summary = stats[0].render()
    assert "Excluded rows without an article: 1" in summary
    assert "Families: 2" in summary
    assert "Articles in default family (UNMAPPED): 1" in summary
    assert "STORE_A: 6 units | cost 70.00 | sale 190.00" in summary
    assert "Total active stores: 6 units | cost 70.00 | sale 190.00" in summary

    raw = pd.read_excel(output_path, sheet_name="RAW")
    assert len(raw) == 2
    assert list(raw.columns) == [
        "SKU_TEST",
        "Color",
        "FAMILY_TEST",
        "STORE_A",
        "STORE_A.Costo",
        "STORE_A.Venta",
        "REGION",
        "REGION.Costo",
        "REGION.Venta",
    ]
    assert raw.loc[0, "SKU_TEST"] == "AA1"
    assert raw.loc[0, "Color"] == "Red"
    assert raw.loc[0, "FAMILY_TEST"] == "Family A"
    assert raw.loc[1, "FAMILY_TEST"] == "UNMAPPED"
    assert raw.loc[0, "STORE_A"] == 5
    assert raw.loc[0, "STORE_A.Costo"] == 50
    assert raw.loc[0, "STORE_A.Venta"] == 150
    assert raw.loc[0, "REGION.Costo"] == 50
    assert raw.loc[0, "REGION.Venta"] == 150
    assert not any(str(column).startswith("__itk_") for column in raw.columns)

    summary = pd.read_excel(output_path, sheet_name="Summary")
    assert summary.columns[0] == "FAMILY_TEST"


@pytest.mark.parametrize("system_units, ignore_negative, difference", [(5, False, -2), (-2, False, 5), (-2, True, 3)])
def test_cross_check_honors_catalog_article_and_family_columns(tmp_path, monkeypatch, system_units, ignore_negative, difference):
    profile = "custom-cross"
    _write_profile(
        tmp_path,
        profile,
        {
            "general/catalog": {
                "version": 3,
                "columns": {"article": "SKU_SYSTEM", "family": "FAMILY_OUT"},
                "default_family": "UNMAPPED",
            },
            "general/families": {
                "version": 3,
                "rules": {"Family A": ["AA"], "REVISAR": ["REVISAR"]},
            },
            "cross_check/settings": {
                "version": 3,
                "input": {"quantity_column": "SYSTEM_UNITS"},
                "reconciliation": {"ignore_negative_system_stock_when_counted": ignore_negative},
                "filters": {"ignored_articles": [], "ignored_terms": []},
                "price_lists": {
                    "cost": {"article_column": "COST_SKU", "price_column": "COST_VALUE"},
                    "sales": {"article_column": "SALES_SKU", "price_column": "SALES_VALUE"},
                },
            },
        },
    )
    monkeypatch.setattr(app_paths, "PROFILES_ROOT", tmp_path / "profiles")

    system_path = tmp_path / "system.xlsx"
    count_path = tmp_path / "count.xlsx"
    cost_path = tmp_path / "cost.xlsx"
    sales_path = tmp_path / "sales.xlsx"
    output_path = tmp_path / "cross.xlsx"

    pd.DataFrame({"SKU_SYSTEM": ["AA1"], "SYSTEM_UNITS": [system_units]}).to_excel(system_path, index=False)
    pd.DataFrame(["AA1", "AA1", "AA1"]).to_excel(count_path, index=False, header=False)
    pd.DataFrame({"COST_SKU": ["AA1"], "COST_VALUE": [10]}).to_excel(cost_path, index=False)
    pd.DataFrame({"SALES_SKU": ["AA1"], "SALES_VALUE": [20]}).to_excel(sales_path, index=False)

    events = []
    stats = []
    result = run_cross_check(
        Namespace(
            cross_check_system=str(system_path),
            cross_check_count=str(count_path),
            shared_cost=str(cost_path),
            shared_sales=str(sales_path),
            cross_check_out=str(output_path),
            cross_check_profile=profile,
            cross_check_consolidate=True,
            cross_check_partial=False,
            non_interactive=True,
            progress=events.append,
            stats=stats.append,
        )
    )
    assert result == str(output_path)
    assert [event.completed for event in events] == [0, 1, 2, 3]
    assert "Reconciliation complete" in events[2].message
    assert "Differences: 1" in stats[0].render()
    assert ("Shortages: 1" if difference < 0 else "Surpluses: 1") in stats[0].render()

    output = pd.read_excel(output_path)
    assert list(output.columns) == [
        "FAMILY_OUT",
        "SKU_SYSTEM",
        "Stock Sistema",
        "Conteo Físico",
        "Diferencia",
        "CTOTAL",
        "VTOTAL",
    ]
    assert output.loc[0, "FAMILY_OUT"] == "Family A"
    assert output.loc[0, "SKU_SYSTEM"] == "AA1"
    assert output.loc[0, "Diferencia"] == difference
    assert output.loc[0, "CTOTAL"] == difference * 10
    assert output.loc[0, "VTOTAL"] == difference * 20


def test_catalog_column_contract_rejects_empty_or_colliding_names():
    from pydantic import ValidationError

    from core.config_schemas import CatalogConfig

    with pytest.raises(ValidationError):
        CatalogConfig.model_validate(
            {
                "version": 3,
                "columns": {"article": "", "family": "Family"},
                "default_family": "Other",
            }
        )

    with pytest.raises(ValidationError):
        CatalogConfig.model_validate(
            {
                "version": 3,
                "columns": {"article": "SKU", "family": "SKU"},
                "default_family": "Other",
            }
        )
