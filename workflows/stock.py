"""Stock Processing, from selected files to a saved report."""

from __future__ import annotations

from argparse import Namespace
from dataclasses import dataclass
from functools import partial

from core.config.configuration_manager import ConfigurationManager
from core.config.profile_config import DEFAULTS
from core.workflow_contracts import category_source_columns, stock_input, stock_price_columns
from workflows.base import Job, choose_columns, remember, require_files, settle_output

MODULE = "stock_processing"
DEFAULT_OUTPUT = "Stock_Valuation_Report.xlsx"


@dataclass(frozen=True)
class StockRequest:
    profile: str
    stock: str
    cost: str
    sales: str
    output: str = ""
    unit_prices: bool = False


def check(request: StockRequest, confirm_column=None) -> dict:
    """Return the headers to read, or raise when an input cannot be used."""
    require_files({"Raw stock": request.stock, "Cost list": request.cost, "Sales list": request.sales})
    remember(request.profile, MODULE, stock=request.stock, cost=request.cost, sales=request.sales)
    config = ConfigurationManager(request.profile, module=MODULE)
    catalog = DEFAULTS["general/catalog"]["columns"]
    prices = DEFAULTS["stock_processing/settings"]["pricing"]["columns"]
    return {
        "stock": choose_columns(
            request.stock,
            {"article": stock_input(config)["article_column"], **category_source_columns(config, MODULE)},
            catalog, confirm_column,
        ),
        "cost": choose_columns(
            request.cost, stock_price_columns(config, "cost", required_only=True), prices, confirm_column),
        "sales": choose_columns(
            request.sales, stock_price_columns(config, "sales", required_only=True), prices, confirm_column),
    }


def prepare(request: StockRequest, columns: dict, notify=None) -> Job:
    request = settle_output(request, MODULE, DEFAULT_OUTPUT, notify)
    return Job(request, partial(_run, request, columns))


def _run(request, columns, *, progress, stats, warnings, on_locked):
    from engine.stock_processing import generator

    return generator.run_stock_processing(Namespace(
        stock_processing_raw=request.stock,
        shared_cost=request.cost,
        shared_sales=request.sales,
        stock_processing_out=request.output,
        stock_processing_profile=request.profile,
        column_overrides=columns,
        include_unit_prices=request.unit_prices,
        on_locked=on_locked,
        progress=progress,
        stats=stats,
        warnings=warnings,
    ))
