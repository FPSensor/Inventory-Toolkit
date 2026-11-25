"""Read and normalize the four Cross Check workbooks."""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial

import pandas as pd

from core.business_schema import ARTICLE_COLUMN, COST_COLUMN, PRICE_COLUMN, QUANTITY_COLUMN
from core.files.data_sanitizer import clean_sku_series
from core.runtime.progress import report_warning
from core.files.table_reader import read_table
from engine.inventory_cross_check.data_processor import SCAN_READING_COLUMN, read_physical_counts


@dataclass
class CrossCheckInputs:
    system: pd.DataFrame
    counts: pd.DataFrame
    costs: pd.DataFrame
    sales: pd.DataFrame


def read_inputs(args, plan) -> CrossCheckInputs:
    notice = partial(report_warning, args)
    return CrossCheckInputs(
        system=_read_system(args.cross_check_system, plan, notice),
        counts=_read_counts(args.cross_check_count, plan, notice),
        costs=_read_prices(args.shared_cost, plan.cost_columns, COST_COLUMN, "cost", plan, notice),
        sales=_read_prices(args.shared_sales, plan.sales_columns, PRICE_COLUMN, "sales", plan, notice),
    )


def _require_columns(frame, columns, label):
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"The {label} workbook is missing configured columns: {missing}.")


def _read_system(path, plan, on_notice):
    frame = read_table(path, text=[plan.system_article], on_notice=on_notice)
    article, quantity = plan.system_article, plan.system_quantity
    _require_columns(
        frame, (article, quantity, *([plan.system_family] if plan.family_mode == "column" else [])), "system stock")
    if article == quantity:
        raise ValueError("System stock article and quantity columns must use different names.")
    renames = {article: ARTICLE_COLUMN, quantity: QUANTITY_COLUMN}
    for source, target in renames.items():
        if source != target and target in frame.columns and target not in renames:
            raise ValueError(f"System stock column '{source}' collides with canonical column '{target}'.")
    frame = frame.rename(columns=renames)
    frame[ARTICLE_COLUMN] = clean_sku_series(frame[ARTICLE_COLUMN])
    frame[QUANTITY_COLUMN] = pd.to_numeric(frame[QUANTITY_COLUMN], errors="coerce").fillna(0)
    return frame


def _read_counts(path, plan, on_notice):
    frame = read_physical_counts(path, plan.count_settings, plan.count_columns, on_notice)
    frame = frame.dropna(subset=[SCAN_READING_COLUMN]).copy()
    frame[SCAN_READING_COLUMN] = clean_sku_series(frame[SCAN_READING_COLUMN])
    return frame


def _read_prices(path, columns, value_label, label, plan, on_notice):
    article, price = columns
    frame = read_table(path, text=[article], on_notice=on_notice)
    _require_columns(frame, columns, f"{label} price list")
    frame = frame.rename(columns={article: ARTICLE_COLUMN, price: value_label})
    articles = clean_sku_series(frame[ARTICLE_COLUMN])
    if plan.first_token_prices:
        articles = articles.apply(lambda value: value.split()[0] if value else value)
    frame[ARTICLE_COLUMN] = articles
    return frame
