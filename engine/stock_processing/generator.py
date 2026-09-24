"""Orchestration for the Stock Processing workflow."""

import os

import numpy as np
import pandas as pd

from core.business_schema import (
    ARTICLE_COLUMN,
    COST_COLUMN,
    FAMILY_COLUMN,
    RAW_DATA_SHEET,
    REVIEW_FAMILY,
    SALES_VALUE_LABEL,
    UNIT_COST_PREFIX,
    UNIT_SALES_PREFIX,
)
from core.configuration_manager import ConfigurationManager
from core.logger import log, log_debug_event
from engine.shared.families import assign_family, build_family_rules
from engine.stock_processing.data_processor import process_pricing
from engine.stock_processing.excel_renderer import render_stock_excel


def run_stock_processing(args):
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
    config = ConfigurationManager(args.stock_processing_profile)

    family_rules = build_family_rules(config.get_family_rules())
    catalog = config.get_catalog()
    network = config.get_network_config()
    stock_config = config.get_stock_processing_config()

    stock_database_columns = network["stock_database_columns"]
    active_stores = network["active"]
    regional_groups = network["regional_groups"]

    cleaning = stock_config["cleaning"]
    pricing = stock_config["pricing"]
    output = stock_config["output"]

    columns_to_drop = cleaning.get("drop_columns", [])
    text_columns = cleaning.get("text_columns", [ARTICLE_COLUMN])
    numeric_columns = cleaning.get("numeric_columns", [])
    base_column_order = output.get("base_columns", [ARTICLE_COLUMN, FAMILY_COLUMN])
    raw_data_sheet = output.get("raw_data_sheet", RAW_DATA_SHEET)
    summaries = output.get("summaries", [])
    log_debug_event(
        "stock_processing_config_loaded",
        family_rule_count=len(family_rules),
        active_store_count=len(active_stores),
        regional_group_count=len(regional_groups),
        stock_database_mapping_count=len(stock_database_columns),
        drop_column_count=len(columns_to_drop),
        text_column_count=len(text_columns),
        numeric_column_count=len(numeric_columns),
        summary_count=len(summaries),
        raw_data_sheet=raw_data_sheet,
    )

    log.info("Processing Stock data...")
    stock_frame = pd.read_excel(args.stock_processing_raw)
    log_debug_event(
        "stock_processing_input_loaded",
        shape=stock_frame.shape,
        columns=list(stock_frame.columns),
    )

    expected_article_column = catalog.get("columns", {}).get("article", ARTICLE_COLUMN)
    if expected_article_column not in stock_frame.columns:
        log.error("APB Error: Stock file is missing the '%s' column.", expected_article_column)
        print(
            f"\n❌ APB Error: The file '{os.path.basename(args.stock_processing_raw)}' "
            f"is NOT a valid Stock file. Missing column '{expected_article_column}'."
        )
        return None

    dropped_columns = [column for column in columns_to_drop if column in stock_frame.columns]
    stock_frame = stock_frame.drop(
        columns=dropped_columns,
        errors="ignore",
    )
    log_debug_event(
        "stock_processing_cleaning_columns",
        dropped_columns=dropped_columns,
        remaining_column_count=len(stock_frame.columns),
    )

    for column in text_columns:
        if column in stock_frame.columns:
            stock_frame[column] = stock_frame[column].astype(str).str.strip()

    for column in numeric_columns:
        if column in stock_frame.columns:
            stock_frame[column] = (
                stock_frame[column]
                .astype(str)
                .str.replace(",", ".", regex=False)
                .str.strip()
            )
            stock_frame[column] = pd.to_numeric(
                stock_frame[column], errors="coerce"
            ).fillna(0).astype(int)

    merged_deposits = []
    for store_column, deposit_column in stock_database_columns.items():
        if store_column in stock_frame.columns and deposit_column in stock_frame.columns:
            stock_frame[store_column] = stock_frame[store_column] + stock_frame[deposit_column]
            stock_frame = stock_frame.drop(columns=[deposit_column])
            merged_deposits.append((store_column, deposit_column))
    log_debug_event(
        "stock_processing_deposit_merge",
        merged_count=len(merged_deposits),
        merged_pairs=merged_deposits,
    )

    for group_name, branches in regional_groups.items():
        stock_frame[group_name] = sum(stock_frame.get(branch, 0) for branch in branches)

    stock_frame[FAMILY_COLUMN] = stock_frame[ARTICLE_COLUMN].apply(
        lambda article: assign_family(article, family_rules)
    )
    family_counts = stock_frame[FAMILY_COLUMN].value_counts(dropna=False)
    log_debug_event(
        "stock_processing_family_assignment",
        row_count=len(stock_frame),
        family_count=int(stock_frame[FAMILY_COLUMN].nunique(dropna=False)),
        review_rows=int(family_counts.get(REVIEW_FAMILY, 0)),
        top_families=family_counts.head(10).to_dict(),
    )

    log.info("Processing pricing files...")
    cost_frame = process_pricing(args.shared_cost, pricing)
    sales_frame = process_pricing(args.shared_sales, pricing)
    log_debug_event(
        "stock_processing_pricing_ready",
        cost_shape=getattr(cost_frame, "shape", None),
        sales_shape=getattr(sales_frame, "shape", None),
        cost_columns=list(cost_frame.columns) if cost_frame is not None else None,
        sales_columns=list(sales_frame.columns) if sales_frame is not None else None,
    )

    if cost_frame is not None:
        cost_renames = {
            column: f"{UNIT_COST_PREFIX}{column}"
            for column in cost_frame.columns
            if column != ARTICLE_COLUMN
        }
        cost_frame = cost_frame.rename(columns=cost_renames)
        stock_frame = pd.merge(stock_frame, cost_frame, on=ARTICLE_COLUMN, how="left")

    if sales_frame is not None:
        sales_renames = {
            column: f"{UNIT_SALES_PREFIX}{column}"
            for column in sales_frame.columns
            if column != ARTICLE_COLUMN
        }
        sales_frame = sales_frame.rename(columns=sales_renames)
        stock_frame = pd.merge(stock_frame, sales_frame, on=ARTICLE_COLUMN, how="left")

    log_debug_event(
        "stock_processing_pricing_merged",
        shape=stock_frame.shape,
        column_count=len(stock_frame.columns),
    )
    unit_price_columns = [
        column for column in stock_frame.columns if column.startswith("PrecioUnit.")
    ]
    stock_frame[unit_price_columns] = stock_frame[unit_price_columns].fillna(-1).astype(float)

    entities_to_value = active_stores + list(regional_groups.keys())
    log_debug_event(
        "stock_processing_valuation_plan",
        entity_count=len(entities_to_value),
        entities=entities_to_value,
        unit_price_column_count=len(unit_price_columns),
    )
    for entity in entities_to_value:
        cost_value_column = f"{entity}.{COST_COLUMN}"
        sales_value_column = f"{entity}.{SALES_VALUE_LABEL}"

        if entity in regional_groups:
            branches = regional_groups[entity]
            stock_frame[cost_value_column] = sum(
                stock_frame.get(f"{branch}.{COST_COLUMN}", 0) for branch in branches
            )
            stock_frame[sales_value_column] = sum(
                stock_frame.get(f"{branch}.{SALES_VALUE_LABEL}", 0) for branch in branches
            )
            continue

        unit_cost_column = f"{UNIT_COST_PREFIX}{entity}"
        unit_sales_column = f"{UNIT_SALES_PREFIX}{entity}"
        if entity in stock_frame.columns:
            stock_frame[cost_value_column] = np.where(
                stock_frame.get(unit_cost_column, 0) <= 0,
                0,
                stock_frame[unit_cost_column] * stock_frame[entity],
            )
            stock_frame[sales_value_column] = np.where(
                stock_frame.get(unit_sales_column, 0) <= 0,
                0,
                stock_frame[unit_sales_column] * stock_frame[entity],
            )

    stock_frame = stock_frame.drop(columns=unit_price_columns, errors="ignore")

    final_column_order = base_column_order.copy()
    for entity in entities_to_value:
        final_column_order.extend(
            [entity, f"{entity}.{COST_COLUMN}", f"{entity}.{SALES_VALUE_LABEL}"]
        )

    stock_frame = stock_frame[
        [column for column in final_column_order if column in stock_frame.columns]
    ]
    log_debug_event(
        "stock_processing_result_ready",
        shape=stock_frame.shape,
        columns=list(stock_frame.columns),
    )

    final_path = render_stock_excel(
        args.stock_processing_out,
        stock_frame,
        summaries,
        stock_frame.columns,
        raw_data_sheet,
        interactive=interactive,
    )
    log.info("Process completed. File saved at: %s", final_path)
    log_debug_event(
        "stock_processing_complete",
        output_file=final_path,
        output_size_bytes=os.path.getsize(final_path) if final_path and os.path.exists(final_path) else None,
        row_count=len(stock_frame),
        column_count=len(stock_frame.columns),
    )
    return final_path
