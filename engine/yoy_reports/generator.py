"""Orchestration for Year-over-Year sales reports."""

from core.configuration_manager import ConfigurationManager
from core.logger import log, log_debug_event
from engine.shared.families import build_family_rules
from engine.yoy_reports.data_processor import process_sales_data
from engine.yoy_reports.excel_renderer import render_yoy_sales_excel
from engine.yoy_reports.metrics import configured_branches, resolve_metric_specs


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
    yoy_include_sizes=None,
    non_interactive=False,
):
    output_config = yoy_config["output"]
    include_sizes = (
        output_config.get("include_sizes", False)
        if yoy_include_sizes is None
        else bool(yoy_include_sizes)
    )
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
        include_sizes=include_sizes,
        metrics=[metric.key for metric in metric_specs],
        annual_comparison=output_config.get("annual_comparison", True),
        non_interactive=non_interactive,
    )
    family_rules = None
    if not yoy_has_families:
        log.info("Loading family rules to dynamically generate groupings...")
        config = ConfigurationManager(profile)
        family_rules = build_family_rules(config.get_family_rules())
        default_family = config.get_default_family()
        log_debug_event(
            "yoy_family_rules_loaded",
            rule_count=len(family_rules),
            default_family=default_family,
        )
    else:
        default_family = "Other"

    log.info("Reading data from %s and filtering dates...", yoy_file_path)
    current_frame, previous_frame, previous_start = process_sales_data(
        yoy_file_path,
        yoy_start_dt,
        yoy_end_dt,
        yoy_config,
        family_rules,
        default_family=default_family,
        grouping_column=yoy_grouping_col,
    )

    log_debug_event(
        "yoy_frames_ready",
        current_shape=current_frame.shape,
        previous_shape=previous_frame.shape,
        previous_start=str(previous_start),
    )
    log.info("Calculating YoY metrics and rendering Excel file...")
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
        include_sizes,
        interactive=not non_interactive,
    )
    log_debug_event("yoy_report_complete", output_file=result)
    return result
