"""Read and normalize the four Cross Check workbooks."""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial

import numpy as np
import pandas as pd

from core.business_schema import ARTICLE_COLUMN, COST_COLUMN, PRICE_COLUMN, QUANTITY_COLUMN
from core.files.data_sanitizer import (
    clean_sku_series,
    describe_unclear_numbers,
    normalize_article_codes,
    parse_numbers,
    read_quantities,
)
from core.runtime.progress import report_warning
from core.files.table_reader import read_table
from engine.inventory_cross_check.data_processor import SCAN_READING_COLUMN, STORE_COLUMN, read_physical_counts


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
    _require_columns(frame, (
        article, quantity, *([plan.system_family] if plan.family_mode == "column" else []),
        *([plan.system_store] if plan.system_store else [])), "system stock")
    if article == quantity:
        raise ValueError("System stock article and quantity columns must use different names.")
    renames = {article: ARTICLE_COLUMN, quantity: QUANTITY_COLUMN}
    for source, target in renames.items():
        if source != target and target in frame.columns and target not in renames:
            raise ValueError(f"System stock column '{source}' collides with canonical column '{target}'.")
    frame = frame.rename(columns=renames)
    if plan.system_store:
        frame[STORE_COLUMN] = frame[plan.system_store].fillna("").astype(str).str.strip()
    frame[ARTICLE_COLUMN] = normalize_article_codes(frame[ARTICLE_COLUMN])
    frame[QUANTITY_COLUMN], unclear = read_quantities(frame[QUANTITY_COLUMN])
    on_notice(describe_unclear_numbers(quantity, unclear))
    unidentified = frame[ARTICLE_COLUMN].eq("") & frame[QUANTITY_COLUMN].ne(0)
    if unidentified.any():
        rows = [int(position) + 2 for position in np.flatnonzero(unidentified.to_numpy())]
        on_notice(
            f"{len(rows)} system stock rows have quantities but no product "
            f"({frame.loc[unidentified, QUANTITY_COLUMN].sum():g} units) and were left out "
            f"(rows {', '.join(map(str, rows[:20]))}{'...' if len(rows) > 20 else ''}). Review the original file.")
    return frame[frame[ARTICLE_COLUMN].ne("")]


def _read_counts(path, plan, on_notice):
    frame = read_physical_counts(path, plan.count_settings, plan.count_columns, on_notice)
    frame = frame.dropna(subset=[SCAN_READING_COLUMN]).copy()
    frame[SCAN_READING_COLUMN] = clean_sku_series(frame[SCAN_READING_COLUMN])
    return frame


def _read_prices(path, columns, value_label, label, plan, on_notice):
    article, price, store = columns
    frame = read_table(path, text=[article], on_notice=on_notice)
    _require_columns(frame, [column for column in columns if column], f"{label} price list")
    if store:
        frame[STORE_COLUMN] = frame[store].fillna("").astype(str).str.strip()
    frame = frame.rename(columns={article: ARTICLE_COLUMN, price: value_label})
    articles = normalize_article_codes(frame[ARTICLE_COLUMN])
    if plan.first_token_prices:
        articles = articles.apply(lambda value: value.split()[0] if value else value)
    frame[ARTICLE_COLUMN] = articles
    values, ambiguous = parse_numbers(frame[value_label])
    on_notice(describe_unclear_numbers(price, ambiguous, f"{label} prices"))
    written = frame[value_label].notna() & frame[value_label].astype(str).str.strip().ne("")
    unreadable = values.isna() & frame[ARTICLE_COLUMN].ne("")
    if unreadable.any():
        rows = [int(position) + 2 for position in np.flatnonzero(unreadable.to_numpy())[:20]]
        raise ValueError(f"The {label} price list has unreadable prices at rows {rows}.")
    frame[value_label] = values
    # A blank price is a missing price, not a price of zero.
    return frame[written & frame[ARTICLE_COLUMN].ne("")]
