"""Orchestration for Year-over-Year sales reports."""

from copy import deepcopy

from core.configuration_manager import ConfigurationManager
from core.logger import log, log_debug_event
from core.progress import report_progress, report_stats
from core.system_utils import normalize_xlsx_output_path
from core.workflow_errors import ErrorCode, WorkflowError
from engine.shared.families import build_family_rules
from engine.yoy_reports.data_processor import process_sales_data
from engine.yoy_reports.excel_renderer import render_yoy_sales_excel
from engine.yoy_reports.metrics import configured_branches, resolve_metric_specs
from engine.yoy_reports.stats import build_yoy_stats


def _require_sales(current, previous, start, end, config, notice):
    """Stop before reporting a fall that only means the file does not cover the period."""
    branch, names = config["input"]["branch_column"], configured_branches(config)
    if not current[branch].isin(names).any():
        raise WorkflowError(
            ErrorCode.PERIOD_WITHOUT_SALES,
            f"The sales file has no rows between {start:%Y-%m-%d} and {end:%Y-%m-%d} for the configured "
            f"locations ({', '.join(names)}). Check the exported dates, the file and the location names.",
        )
    if not previous[branch].isin(names).any():
        notice("The sales file has no rows for the same period of the previous year, so there is nothing to compare.")


def generate_sales_report(
    yoy_file_path,
    yoy_output_path,
    yoy_start_dt,
    yoy_end_dt,
    yoy_config,
    yoy_grouping_col,
    yoy_segmented,
    yoy_has_families,
    profile,
    yoy_include_variants=None,
    on_locked=None,
    progress=None,
    stats=None,
    warnings=None,
):
    report_progress(progress, 0, 3, "Reading sales and selecting comparison periods...")
    yoy_output_path = normalize_xlsx_output_path(yoy_output_path)
    output_config = yoy_config["output"]
    include_variants = (
        output_config.get("include_variants", False)
        if yoy_include_variants is None
        else bool(yoy_include_variants)
    )
    yoy_config = deepcopy(yoy_config)
    yoy_config["output"]["include_variants"] = include_variants
    metric_specs = resolve_metric_specs(yoy_config)
    configured_branches(yoy_config)

    log_debug_event(
        "yoy_report_start",
        profile=profile,
        input_file=yoy_file_path,
        output_file=yoy_output_path,
        start=str(yoy_start_dt),
        end=str(yoy_end_dt),
        grouping_column=yoy_grouping_col,
        segmented=yoy_segmented,
        has_families=yoy_has_families,
        include_variants=include_variants,
        metrics=[metric.key for metric in metric_specs],
        annual_comparison=output_config.get("annual_comparison", True),
    )
    family_rules = None
    if not yoy_has_families:
        log.info("Loading family rules to dynamically generate groupings...")
        config = ConfigurationManager(profile, module="yoy_reports")
        family_rules = build_family_rules(config.get_family_rules())
        default_family = config.get_default_family()
        log_debug_event(
            "yoy_family_rules_loaded",
            rule_count=len(family_rules),
            default_family=default_family,
        )
    else:
        default_family = "Other"

    notice = log.warning if warnings is None else warnings.append
    log.info("Reading data from %s and filtering dates...", yoy_file_path)
    current_frame, previous_frame, previous_start = process_sales_data(
        yoy_file_path,
        yoy_start_dt,
        yoy_end_dt,
        yoy_config,
        family_rules,
        default_family=default_family,
        grouping_column=yoy_grouping_col,
        on_notice=notice,
    )
    _require_sales(current_frame, previous_frame, yoy_start_dt, yoy_end_dt, yoy_config, notice)

    log_debug_event(
        "yoy_frames_ready",
        current_shape=current_frame.shape,
        previous_shape=previous_frame.shape,
        previous_start=str(previous_start),
    )
    report_progress(progress, 1, 3, "Sales loaded and comparison periods selected. Calculating metrics...")
    log.info("Calculating YoY metrics and rendering Excel file...")
    report_progress(progress, 2, 3, "Calculating configured metrics and preparing report sheets...")
    result = render_yoy_sales_excel(
        yoy_output_path,
        current_frame,
        previous_frame,
        yoy_start_dt,
        yoy_end_dt,
        previous_start,
        yoy_config,
        yoy_grouping_col,
        yoy_segmented,
        include_variants,
        on_locked=on_locked,
        progress=progress,
    )
    report_progress(progress, 3, 3, "YoY report saved.")
    if stats is not None:
        report_stats(stats, *build_yoy_stats(current_frame, previous_frame, yoy_start_dt, yoy_end_dt, yoy_config))
    log_debug_event("yoy_report_complete", output_file=result)
    return result
