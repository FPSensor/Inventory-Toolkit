"""Inventory Cross Check, from selected files to a saved report."""

from __future__ import annotations

from argparse import Namespace
from dataclasses import dataclass
from functools import partial

from core.configuration_manager import ConfigurationManager
from core.profile_config import DEFAULTS
from core.workflow_contracts import category_source_columns, cross_article_column
from workflows.base import Job, choose_columns, remember, require_files, settle_output

MODULE = "cross_check"
DEFAULT_OUTPUT = "Cross_Check_Output.xlsx"


@dataclass(frozen=True)
class CrossRequest:
    profile: str
    system: str
    count: str
    cost: str
    sales: str
    output: str = ""
    consolidate: bool = False
    partial_count: bool = False


def check(request: CrossRequest, confirm_column=None) -> dict:
    """Return the headers to read, or raise when an input cannot be used."""
    require_files({"System stock": request.system, "Physical count": request.count,
                   "Cost list": request.cost, "Sales list": request.sales})
    remember(request.profile, MODULE, system=request.system, count=request.count,
             cost=request.cost, sales=request.sales)
    config = ConfigurationManager(request.profile, module=MODULE)
    settings = config.get_cross_check_config()
    source, lists = settings["input"], settings["price_lists"]
    catalog = DEFAULTS["general/catalog"]["columns"]
    defaults = DEFAULTS["cross_check/settings"]
    columns = {
        "system": choose_columns(
            request.system,
            {"article": cross_article_column(config), "quantity": source["quantity_column"],
             **category_source_columns(config, MODULE)},
            {**catalog, "quantity": defaults["input"]["quantity_column"]}, confirm_column,
        ),
        "cost": choose_columns(request.cost, lists["cost"], defaults["price_lists"]["cost"], confirm_column),
        "sales": choose_columns(request.sales, lists["sales"], defaults["price_lists"]["sales"], confirm_column),
    }
    if source["count_mode"] == "quantities":
        columns["count"] = choose_columns(
            request.count,
            {"article": source["count_article_column"], "quantity": source["count_quantity_column"]},
            {**catalog, "quantity": source["quantity_column"]}, confirm_column,
        )
    return columns


def prepare(request: CrossRequest, columns: dict, notify=None) -> Job:
    request = settle_output(request, MODULE, DEFAULT_OUTPUT, notify)
    return Job(request, partial(_run, request, columns))


def _run(request, columns, *, progress, stats, warnings, interactive):
    from engine.inventory_cross_check import generator

    return generator.run_cross_check(Namespace(
        cross_check_system=request.system,
        cross_check_count=request.count,
        shared_cost=request.cost,
        shared_sales=request.sales,
        cross_check_out=request.output,
        cross_check_profile=request.profile,
        cross_check_consolidate=request.consolidate,
        cross_check_partial=request.partial_count,
        column_overrides=columns,
        non_interactive=not interactive,
        progress=progress,
        stats=stats,
        warnings=warnings,
    ))
