"""Year-over-Year sales, from a sales file to a saved report."""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial

import pandas as pd

from core.configuration_manager import ConfigurationManager
from core.profile_config import DEFAULTS
from core.workflow_errors import ErrorCode, WorkflowError
from workflows.base import Job, choose_columns, remember, require_files, settle_output

MODULE = "yoy_reports"


@dataclass(frozen=True)
class YoYRequest:
    profile: str
    sales: str
    start: str = ""
    end: str = ""
    by_family: bool = True
    has_families: bool = True
    sales_amounts: bool = False
    by_month: bool = False
    annual_comparison: bool = False
    variants: bool = False
    output: str = ""


def settings(profile: str) -> dict:
    return ConfigurationManager(profile, module=MODULE).get_yoy_reports_config()


def check_file(request: YoYRequest) -> None:
    require_files({"Sales data": request.sales})
    remember(request.profile, MODULE, file=request.sales)


def period(start: str, end: str):
    """Return the whole-day period, or raise when it cannot be read."""
    try:
        first, last = (pd.to_datetime(text.strip(), format="%Y-%m-%d") for text in (start, end))
    except ValueError as exc:
        raise WorkflowError(ErrorCode.PERIOD_INVALID, "Dates must use YYYY-MM-DD (e.g. 2026-01-31).") from exc
    if pd.isna(first) or pd.isna(last) or first > last:
        raise WorkflowError(ErrorCode.PERIOD_INVALID, "Enter a start date that is not later than the end date.")
    return first, last + pd.Timedelta(days=1, seconds=-1)


def check(request: YoYRequest, confirm_column=None) -> dict:
    """Return this run's configuration, or raise when an input cannot be used."""
    from engine.yoy_reports.metrics import select_run_metrics

    check_file(request)
    period(request.start, request.end)
    config = select_run_metrics(settings(request.profile), request.sales_amounts)
    if not request.by_month:
        config["output"]["annual_comparison"] = request.annual_comparison
    fields = [
        "date_column", "branch_column",
        *("quantity_column" if metric == "units" else "sales_column" for metric in config["output"]["metrics"]),
        "grouping_column" if request.by_family and request.has_families else "item_column",
        *(["variant_column"] if request.variants else []),
    ]
    config["input"].update(choose_columns(
        request.sales, {field: config["input"][field] for field in dict.fromkeys(fields)},
        DEFAULTS["yoy_reports/settings"]["input"], confirm_column,
    ))
    return config


def prepare(request: YoYRequest, config: dict, notify=None) -> Job:
    request = settle_output(request, MODULE, config["output"]["default_path"], notify)
    return Job(request, partial(_run, request, config))


def _run(request, config, *, progress, stats, warnings, interactive):
    from engine.yoy_reports import generator

    start, end = period(request.start, request.end)
    return generator.generate_sales_report(
        request.sales, request.output, start, end, config,
        config["input"]["grouping_column" if request.by_family else "item_column"],
        request.by_month, request.has_families or not request.by_family, request.profile, request.variants,
        non_interactive=not interactive, progress=progress, stats=stats,
    )
