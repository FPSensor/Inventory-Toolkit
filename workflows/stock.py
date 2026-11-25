"""Stock Processing, from selected files to a saved report."""

from __future__ import annotations

import time
from argparse import Namespace
from collections.abc import Mapping
from dataclasses import dataclass, replace

from core.configuration_manager import ConfigurationManager
from core.input_columns import choose_input_columns
from core.logger import log_debug_event
from core.profile_config import DEFAULTS
from core.profile_store import save_last_paths
from core.system_utils import normalize_xlsx_output_path
from core.workflow_contracts import category_source_columns, stock_input, stock_price_columns
from workflows.base import ConfirmColumn, RunResult, require_files, require_output

DEFAULT_OUTPUT = "Stock_Valuation_Report.xlsx"
Columns = Mapping[str, Mapping[str, str]]


@dataclass(frozen=True)
class StockRequest:
    profile: str
    stock: str
    cost: str
    sales: str
    output: str = ""
    unit_prices: bool = False


def check(request: StockRequest, confirm_column: ConfirmColumn | None = None) -> Columns:
    """Return the headers to read, or raise when an input cannot be used."""
    require_files({"Raw stock": request.stock, "Cost list": request.cost, "Sales list": request.sales})
    config = ConfigurationManager(request.profile, module="stock_processing")
    catalog = DEFAULTS["general/catalog"]["columns"]
    prices = DEFAULTS["stock_processing/settings"]["pricing"]["columns"]

    def choose(path, configured, defaults):
        confirm = None if confirm_column is None else lambda *question: confirm_column(path, *question)
        return choose_input_columns(path, configured, defaults, confirm)

    return {
        "stock": choose(
            request.stock,
            {"article": stock_input(config)["article_column"], **category_source_columns(config, "stock_processing")},
            {"article": catalog["article"], "family": catalog["family"]},
        ),
        "cost": choose(request.cost, stock_price_columns(config, "cost", required_only=True), prices),
        "sales": choose(request.sales, stock_price_columns(config, "sales", required_only=True), prices),
    }


def prepare(request: StockRequest, columns: Columns, notify=None) -> "StockJob":
    """Settle the output name and remember this selection for the next run."""
    output = normalize_xlsx_output_path(request.output.strip() or DEFAULT_OUTPUT, notify=notify)
    request = replace(request, output=output)
    save_last_paths(request.profile, {"stock_processing": {
        "stock": request.stock, "cost": request.cost, "sales": request.sales, "out": output,
    }})
    return StockJob(request, columns)


@dataclass(frozen=True)
class StockJob:
    """A verified request. It asks nothing, so it can run on any thread."""

    request: StockRequest
    columns: Columns

    def run(self, *, progress=None, stats=None, interactive=False) -> RunResult:
        from engine.stock_processing import generator

        request, warnings, started = self.request, [], time.time()
        output = generator.run_stock_processing(Namespace(
            stock_processing_raw=request.stock,
            shared_cost=request.cost,
            shared_sales=request.sales,
            stock_processing_out=request.output,
            stock_processing_profile=request.profile,
            column_overrides=self.columns,
            include_unit_prices=request.unit_prices,
            non_interactive=not interactive,
            progress=progress,
            stats=stats,
            warnings=warnings,
        ))
        result = require_output(output, time.time() - started, warnings)
        log_debug_event("stock_workflow_complete", output=result.output, elapsed_seconds=round(result.elapsed, 4))
        return result
