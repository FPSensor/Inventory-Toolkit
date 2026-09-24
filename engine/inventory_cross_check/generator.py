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
)
from core.configuration_manager import ConfigurationManager
from core.data_sanitizer import clean_sku_series
from core.logger import log
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

    with execution_timer("Data Transformation & Matching"):
        system_frame[ARTICLE_COLUMN] = clean_sku_series(system_frame[ARTICLE_COLUMN])
        system_frame[QUANTITY_COLUMN] = pd.to_numeric(
            system_frame[QUANTITY_COLUMN],
            errors="coerce",
        ).fillna(0)
        master_articles = system_frame[ARTICLE_COLUMN].unique().tolist()
        master_set = {str(article).upper().strip() for article in master_articles}

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
    return final_path
