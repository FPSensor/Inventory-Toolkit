from argparse import Namespace

import pandas as pd
import pytest

from core.system_utils import InvalidExcelOutputPathError
from engine.inventory_cross_check.generator import run_cross_check
from engine.stock_processing.generator import run_stock_processing
from engine.yoy_reports.generator import generate_sales_report


def test_stock_rejects_xls_output_before_input_validation():
    with pytest.raises(InvalidExcelOutputPathError):
        run_stock_processing(
            Namespace(
                stock_processing_raw="missing-stock.xlsx",
                shared_cost="missing-cost.xlsx",
                shared_sales="missing-sales.xlsx",
                stock_processing_out="result.xls",
                stock_processing_profile="demo",
                non_interactive=True,
            )
        )


def test_cross_rejects_xls_output_before_input_validation():
    with pytest.raises(InvalidExcelOutputPathError):
        run_cross_check(
            Namespace(
                cross_check_system="missing-system.xls",
                cross_check_count="missing-count.xlsx",
                shared_cost="missing-cost.xlsx",
                shared_sales="missing-sales.xlsx",
                cross_check_out="result.xls",
                cross_check_profile="demo",
                cross_check_consolidate=False,
                cross_check_partial=False,
                non_interactive=True,
            )
        )


def test_yoy_rejects_xls_output_before_reading_sales_data(monkeypatch):
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("YoY input processing must not start for an invalid output path")

    monkeypatch.setattr(
        "engine.yoy_reports.generator.process_sales_data",
        fail_if_called,
    )

    yoy_config = {
        "input": {
            "date_column": "Fecha",
            "quantity_column": "Cantidad",
            "sales_column": "Monto",
            "grouping_column": "Familias",
            "item_column": "Articulo",
            "branch_column": "Base",
            "size_column": "Talle",
        },
        "output": {
            "default_path": "report.xlsx",
            "metrics": ["units"],
            "annual_comparison": True,
            "include_sizes": False,
        },
        "groups": {"All": ["STORE"]},
    }

    with pytest.raises(InvalidExcelOutputPathError):
        generate_sales_report(
            "missing-sales.xlsx",
            "result.xls",
            pd.Timestamp("2026-01-01"),
            pd.Timestamp("2026-01-31"),
            yoy_config,
            "Familias",
            False,
            True,
            "demo",
            non_interactive=True,
        )
