"""Orchestration for the Inventory Cross Check workflow."""

import gc
import os

import pandas as pd

from core.business_schema import (
    ARTICLE_COLUMN,
    COST_COLUMN,
    COST_TOTAL_COLUMN,
    DIFFERENCE_COLUMN,
    FAMILY_COLUMN,
    PHYSICAL_COUNT_COLUMN,
    PRICE_COLUMN,
    QUANTITY_COLUMN,
    SALES_TOTAL_COLUMN,
    SYSTEM_STOCK_COLUMN,
    REVIEW_PREFIX,
)
from core.configuration_manager import ConfigurationManager
from core.data_sanitizer import clean_sku_series
from core.logger import log, log_debug_event
from core.system_utils import safe_pandas_to_excel
from core.telemetry import execution_timer
from engine.inventory_cross_check.data_processor import (
    calculate_difference,
    normalize_article,
)
from engine.inventory_cross_check.excel_renderer import apply_excel_formatting
from engine.shared.families import assign_families, build_family_rules

_SCAN_READING_COLUMN = "__scan_reading"
_SCAN_COUNT_COLUMN = "__scan_count"


def run_cross_check(args):
    interactive = not getattr(args, "non_interactive", False)
    log_debug_event(
        "cross_check_start",
        profile=args.cross_check_profile,
        system_file=args.cross_check_system,
        count_file=args.cross_check_count,
        cost_file=args.shared_cost,
        sales_file=args.shared_sales,
        output_file=args.cross_check_out,
        consolidate=args.cross_check_consolidate,
        partial=args.cross_check_partial,
        interactive=interactive,
    )
    required_files = [
        args.cross_check_system,
        args.cross_check_count,
        args.shared_cost,
        args.shared_sales,
    ]
    for file_path in required_files:
        if not os.path.exists(file_path):
            log.error("File not found: '%s'", file_path)
            return None

    config = ConfigurationManager(profile=args.cross_check_profile)
    family_rules = build_family_rules(config.get_family_rules())
    default_family = config.get_default_family()
    cross_check_config = config.get_cross_check_config()

    filters = cross_check_config["filters"]
    ignored_articles = filters.get("ignored_articles", [])
    ignored_terms = filters.get("ignored_terms", [])

    price_lists = cross_check_config["price_lists"]
    cost_columns = price_lists.get("cost", {})
    sales_columns = price_lists.get("sales", {})
    cost_article_column = cost_columns.get("article_column", ARTICLE_COLUMN)
    cost_price_column = cost_columns.get("price_column", PRICE_COLUMN)
    sales_article_column = sales_columns.get("article_column", ARTICLE_COLUMN)
    sales_price_column = sales_columns.get("price_column", PRICE_COLUMN)
    log_debug_event(
        "cross_check_config_loaded",
        family_rule_count=len(family_rules),
        default_family=default_family,
        ignored_article_count=len(ignored_articles),
        ignored_term_count=len(ignored_terms),
        cost_article_column=cost_article_column,
        cost_price_column=cost_price_column,
        sales_article_column=sales_article_column,
        sales_price_column=sales_price_column,
    )

    with execution_timer("Read and Validate Spreadsheets"):
        system_frame = pd.read_excel(args.cross_check_system)
        if ARTICLE_COLUMN not in system_frame.columns or QUANTITY_COLUMN not in system_frame.columns:
            log.error(
                "Missing '%s' or '%s' in system stock.",
                ARTICLE_COLUMN,
                QUANTITY_COLUMN,
            )
            return None

        count_frame = pd.read_excel(
            args.cross_check_count,
            header=None,
            names=[_SCAN_READING_COLUMN],
        )
        cost_frame = pd.read_excel(args.shared_cost)
        sales_frame = pd.read_excel(args.shared_sales)
        log_debug_event(
            "cross_check_inputs_loaded",
            system_shape=system_frame.shape,
            count_shape=count_frame.shape,
            cost_shape=cost_frame.shape,
            sales_shape=sales_frame.shape,
            system_columns=list(system_frame.columns),
            cost_columns=list(cost_frame.columns),
            sales_columns=list(sales_frame.columns),
        )

    with execution_timer("Data Transformation & Matching"):
        system_frame[ARTICLE_COLUMN] = clean_sku_series(system_frame[ARTICLE_COLUMN])
        system_frame[QUANTITY_COLUMN] = pd.to_numeric(
            system_frame[QUANTITY_COLUMN],
            errors="coerce",
        ).fillna(0)
        raw_master_articles = system_frame[ARTICLE_COLUMN].unique().tolist()
        master_articles = [article for article in raw_master_articles if article]
        master_set = {str(article).upper().strip() for article in master_articles}
        log_debug_event(
            "cross_check_master_catalog",
            system_rows=len(system_frame),
            unique_articles=len(master_articles),
            ignored_empty_article_rows=int((system_frame[ARTICLE_COLUMN] == "").sum()),
        )

        cost_frame.rename(
            columns={cost_article_column: ARTICLE_COLUMN, cost_price_column: COST_COLUMN},
            inplace=True,
        )
        sales_frame.rename(
            columns={sales_article_column: ARTICLE_COLUMN, sales_price_column: PRICE_COLUMN},
            inplace=True,
        )
        cost_frame[ARTICLE_COLUMN] = clean_sku_series(cost_frame[ARTICLE_COLUMN]).apply(
            lambda article: article.split()[0] if article else article
        )
        sales_frame[ARTICLE_COLUMN] = clean_sku_series(sales_frame[ARTICLE_COLUMN]).apply(
            lambda article: article.split()[0] if article else article
        )

        count_frame = count_frame.dropna(subset=[_SCAN_READING_COLUMN]).copy()
        count_frame[_SCAN_READING_COLUMN] = clean_sku_series(count_frame[_SCAN_READING_COLUMN])
        count_frame[_SCAN_COUNT_COLUMN] = 1
        count_frame[ARTICLE_COLUMN] = count_frame[_SCAN_READING_COLUMN].apply(
            lambda reading: normalize_article(reading, master_articles, master_set)
        )
        review_count = int(
            count_frame[ARTICLE_COLUMN].astype(str).str.startswith(REVIEW_PREFIX).sum()
        )
        log_debug_event(
            "cross_check_scanner_normalization",
            raw_readings=len(count_frame),
            unique_normalized_articles=count_frame[ARTICLE_COLUMN].nunique(dropna=False),
            review_count=review_count,
        )

        if args.cross_check_consolidate:
            system_consolidated = system_frame.groupby(
                ARTICLE_COLUMN,
                as_index=False,
            )[QUANTITY_COLUMN].sum()
        else:
            system_consolidated = system_frame[[ARTICLE_COLUMN, QUANTITY_COLUMN]].copy()
        system_consolidated.rename(
            columns={QUANTITY_COLUMN: SYSTEM_STOCK_COLUMN},
            inplace=True,
        )

        count_consolidated = (
            count_frame.groupby(ARTICLE_COLUMN, as_index=False)[_SCAN_COUNT_COLUMN]
            .sum()
            .rename(columns={_SCAN_COUNT_COLUMN: PHYSICAL_COUNT_COLUMN})
        )
        cost_consolidated = cost_frame.groupby(ARTICLE_COLUMN, as_index=False)[COST_COLUMN].mean()
        sales_consolidated = sales_frame.groupby(ARTICLE_COLUMN, as_index=False)[PRICE_COLUMN].mean()

        merge_mode = "left" if args.cross_check_partial else "outer"
        reconciliation = pd.merge(
            count_consolidated,
            system_consolidated,
            on=ARTICLE_COLUMN,
            how=merge_mode,
        ).fillna(0)
        rows_before_filters = len(reconciliation)
        log_debug_event(
            "cross_check_consolidation",
            merge_mode=merge_mode,
            system_rows=len(system_consolidated),
            count_rows=len(count_consolidated),
            reconciliation_rows=rows_before_filters,
        )

        if ignored_articles:
            reconciliation = reconciliation[
                ~reconciliation[ARTICLE_COLUMN].isin(ignored_articles)
            ]
        for ignored_term in ignored_terms:
            reconciliation = reconciliation[
                ~reconciliation[ARTICLE_COLUMN]
                .astype(str)
                .str.contains(ignored_term, case=False, na=False)
            ]

        log_debug_event(
            "cross_check_filters_applied",
            rows_before=rows_before_filters,
            rows_after=len(reconciliation),
            rows_removed=rows_before_filters - len(reconciliation),
        )

        reconciliation[DIFFERENCE_COLUMN] = [
            calculate_difference(system_stock, physical_count)
            for system_stock, physical_count in zip(
                reconciliation[SYSTEM_STOCK_COLUMN],
                reconciliation[PHYSICAL_COUNT_COLUMN],
            )
        ]
        reconciliation[FAMILY_COLUMN] = assign_families(
            reconciliation[ARTICLE_COLUMN],
            family_rules,
            default_family=default_family,
        )

        result = reconciliation.merge(
            cost_consolidated,
            on=ARTICLE_COLUMN,
            how="left",
        ).merge(
            sales_consolidated,
            on=ARTICLE_COLUMN,
            how="left",
        )
        result[COST_TOTAL_COLUMN] = result[DIFFERENCE_COLUMN] * result[COST_COLUMN].fillna(0)
        result[SALES_TOTAL_COLUMN] = result[DIFFERENCE_COLUMN] * result[PRICE_COLUMN].fillna(0)

        result = result[result[DIFFERENCE_COLUMN] != 0].copy()
        output_columns = [
            FAMILY_COLUMN,
            ARTICLE_COLUMN,
            SYSTEM_STOCK_COLUMN,
            PHYSICAL_COUNT_COLUMN,
            DIFFERENCE_COLUMN,
            COST_TOTAL_COLUMN,
            SALES_TOTAL_COLUMN,
        ]
        result = result[output_columns].sort_values(by=[FAMILY_COLUMN, ARTICLE_COLUMN])
        log_debug_event(
            "cross_check_result_ready",
            difference_rows=len(result),
            family_count=result[FAMILY_COLUMN].nunique(dropna=False),
            positive_differences=int((result[DIFFERENCE_COLUMN] > 0).sum()),
            negative_differences=int((result[DIFFERENCE_COLUMN] < 0).sum()),
            zero_cost_total_rows=int((result[COST_TOTAL_COLUMN] == 0).sum()),
            zero_sales_total_rows=int((result[SALES_TOTAL_COLUMN] == 0).sum()),
        )

    with execution_timer("Excel Rendering & Formatting"):
        final_path = safe_pandas_to_excel(
            result,
            args.cross_check_out,
            index=False,
            interactive=interactive,
        )
        apply_excel_formatting(final_path, interactive=interactive)

    del system_frame, count_frame, cost_frame, sales_frame, reconciliation, result
    gc.collect()

    log.info("Reconciliation completed successfully: %s", final_path)
    log_debug_event(
        "cross_check_complete",
        output_file=final_path,
        output_size_bytes=os.path.getsize(final_path) if final_path and os.path.exists(final_path) else None,
        garbage_collected=True,
    )
    return final_path
