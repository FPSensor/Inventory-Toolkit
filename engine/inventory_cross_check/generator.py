"""Orchestration for the Inventory Cross Check workflow."""

from __future__ import annotations

from core.business_schema import DIFFERENCE_COLUMN
from core.configuration_manager import ConfigurationManager
from core.logger import log, log_debug_event
from core.progress import report_progress, report_stats
from core.system_utils import normalize_xlsx_output_path, require_input_files, safe_pandas_to_excel
from core.telemetry import execution_timer
from engine.inventory_cross_check.contracts import CrossCheckPlan
from engine.inventory_cross_check.excel_renderer import apply_excel_formatting
from engine.inventory_cross_check.inputs import read_inputs
from engine.inventory_cross_check.reconciliation import reconcile


def run_cross_check(args):
    """Reconcile a physical count with system stock and save the differences."""
    output_path = normalize_xlsx_output_path(args.cross_check_out)
    on_locked = getattr(args, "on_locked", None)
    progress = getattr(args, "progress", None)
    report_progress(progress, 0, 3, "Reading system stock, scanner readings and price lists...")
    require_input_files(args.cross_check_system, args.cross_check_count, args.shared_cost, args.shared_sales)
    plan = CrossCheckPlan.from_manager(
        ConfigurationManager(profile=args.cross_check_profile, module="cross_check"),
        getattr(args, "column_overrides", {}),
    )

    with execution_timer("Read and Validate Spreadsheets"):
        inputs = read_inputs(args, plan)
        log_debug_event(
            "cross_check_inputs_loaded",
            profile=args.cross_check_profile,
            system_shape=inputs.system.shape,
            count_shape=inputs.counts.shape,
            cost_shape=inputs.costs.shape,
            sales_shape=inputs.sales.shape,
        )
    report_progress(progress, 1, 3, "Files loaded. Matching and reconciling articles...")

    with execution_timer("Data Transformation & Matching"):
        result = reconcile(
            inputs, plan, consolidate=args.cross_check_consolidate, partial=args.cross_check_partial)
    differences = result.report[DIFFERENCE_COLUMN]
    report_progress(progress, 2, 3, "Reconciliation complete. Writing workbook...")

    with execution_timer("Excel Rendering & Formatting"):
        final_path = safe_pandas_to_excel(result.report, output_path, index=False, on_locked=on_locked)
        apply_excel_formatting(final_path, on_locked=on_locked)
    report_progress(progress, 3, 3, "Cross-check report saved.")
    report_stats(
        getattr(args, "stats", None),
        f"Differences: {len(result.report):,}",
        f"Surpluses: {int((differences > 0).sum()):,}",
        f"Shortages: {int((differences < 0).sum()):,}",
        f"Scanner readings to review: {result.readings_to_review:,}",
        f"Families with differences: {result.report[plan.family_label].nunique(dropna=False):,}",
        f"Catalog articles: {result.catalog_articles:,}",
        f"Articles filtered: {result.filtered_articles:,}",
    )
    log.info("Reconciliation completed successfully: %s", final_path)
    log_debug_event("cross_check_complete", output_file=final_path, rows=len(result.report))
    return final_path
