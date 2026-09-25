"""High-level orchestration for the Stock Processing workflow."""

from __future__ import annotations

import os

import pandas as pd

from core.configuration_manager import ConfigurationManager
from core.logger import log, log_debug_event
from core.telemetry import execution_timer
from engine.shared.families import build_family_rules
from engine.stock_processing.contracts import StockProcessingPlan
from engine.stock_processing.data_processor import (
    add_regional_groups,
    classify_stock_families,
    merge_stock_database_columns,
    prepare_stock_frame,
    project_stock_output,
)
from engine.stock_processing.excel_renderer import render_stock_excel
from engine.stock_processing.pricing import process_pricing
from engine.stock_processing.valuation import (
    attach_unit_prices,
    calculate_inventory_values,
    remove_unit_prices,
)


def _load_plan(profile: str) -> StockProcessingPlan:
    config = ConfigurationManager(profile)
    return StockProcessingPlan.from_manager(config)


def _log_plan(plan: StockProcessingPlan) -> None:
    log_debug_event(
        "stock_processing_config_loaded",
        article_column=plan.article_column,
        family_column=plan.family_column,
        family_rule_count=sum(len(prefixes) for prefixes in plan.family_rules.values()),
        default_family=plan.default_family,
        active_store_count=len(plan.active_stores),
        regional_group_count=len(plan.regional_groups),
        stock_database_mapping_count=len(plan.stock_database_columns),
        drop_column_count=len(plan.drop_columns),
        text_column_count=len(plan.text_columns),
        numeric_column_count=len(plan.numeric_columns),
        summary_count=len(plan.summaries),
        raw_data_sheet=plan.raw_data_sheet,
    )


def run_stock_processing(args):
    """Execute the profile-driven stock cleanup, pricing, valuation and export pipeline."""
    interactive = not getattr(args, "non_interactive", False)
    log_debug_event(
        "stock_processing_start",
        profile=args.stock_processing_profile,
        stock_file=args.stock_processing_raw,
        cost_file=args.shared_cost,
        sales_file=args.shared_sales,
        output_file=args.stock_processing_out,
        interactive=interactive,
    )

    required_files = [args.stock_processing_raw, args.shared_cost, args.shared_sales]
    for file_path in required_files:
        if not os.path.exists(file_path):
            log.error("Data file '%s' not found.", file_path)
            return None

    log.info("Loading configurations for profile: %s...", args.stock_processing_profile)
    plan = _load_plan(args.stock_processing_profile)
    family_rules = build_family_rules(plan.family_rules)
    _log_plan(plan)

    with execution_timer("Stock Input & Cleaning"):
        log.info("Processing Stock data...")
        raw_frame = pd.read_excel(args.stock_processing_raw)
        log_debug_event(
            "stock_processing_input_loaded",
            shape=raw_frame.shape,
            columns=list(raw_frame.columns),
        )
        try:
            stock_frame = prepare_stock_frame(raw_frame, plan)
        except ValueError as exc:
            log.error("APB Error: %s", exc)
            print(
                f"\n❌ APB Error: The file '{os.path.basename(args.stock_processing_raw)}' "
                f"is NOT a valid Stock file. {exc}"
            )
            return None

    with execution_timer("Stock Network & Classification"):
        stock_frame, merged_deposits = merge_stock_database_columns(
            stock_frame,
            plan.stock_database_columns,
        )
        log_debug_event(
            "stock_processing_deposit_merge",
            merged_count=len(merged_deposits),
            merged_pairs=merged_deposits,
        )

        stock_frame = add_regional_groups(stock_frame, plan.regional_groups)
        stock_frame = classify_stock_families(
            stock_frame,
            family_rules,
            default_family=plan.default_family,
        )

    with execution_timer("Stock Pricing & Valuation"):
        log.info("Processing pricing files...")
        cost_frame = process_pricing(args.shared_cost, plan.pricing)
        sales_frame = process_pricing(args.shared_sales, plan.pricing)
        log_debug_event(
            "stock_processing_pricing_ready",
            cost_shape=getattr(cost_frame, "shape", None),
            sales_shape=getattr(sales_frame, "shape", None),
            cost_columns=list(cost_frame.columns) if cost_frame is not None else None,
            sales_columns=list(sales_frame.columns) if sales_frame is not None else None,
        )

        stock_frame, unit_price_columns = attach_unit_prices(
            stock_frame,
            cost_frame,
            sales_frame,
        )
        log_debug_event(
            "stock_processing_pricing_merged",
            shape=stock_frame.shape,
            column_count=len(stock_frame.columns),
        )
        log_debug_event(
            "stock_processing_valuation_plan",
            entity_count=len(plan.entities_to_value),
            entities=list(plan.entities_to_value),
            unit_price_column_count=len(unit_price_columns),
        )

        stock_frame = calculate_inventory_values(stock_frame, plan)
        stock_frame = remove_unit_prices(stock_frame, unit_price_columns)
        result_frame = project_stock_output(stock_frame, plan)
        log_debug_event(
            "stock_processing_result_ready",
            shape=result_frame.shape,
            columns=list(result_frame.columns),
        )

    with execution_timer("Stock Excel Rendering"):
        final_path = render_stock_excel(
            args.stock_processing_out,
            result_frame,
            plan.summaries,
            result_frame.columns,
            plan.raw_data_sheet,
            family_column=plan.family_column,
            interactive=interactive,
        )

    log.info("Process completed. File saved at: %s", final_path)
    log_debug_event(
        "stock_processing_complete",
        output_file=final_path,
        output_size_bytes=(
            os.path.getsize(final_path)
            if final_path and os.path.exists(final_path)
            else None
        ),
        row_count=len(result_frame),
        column_count=len(result_frame.columns),
    )
    return final_path
