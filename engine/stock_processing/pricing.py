"""Price-list ingestion and normalization for Stock Processing."""

from __future__ import annotations

import os

import pandas as pd

from core.files.data_sanitizer import describe_unclear_numbers, normalize_article_codes, parse_numbers
from core.runtime.logger import log_debug_event, log_exception
from core.files.table_reader import read_table
from engine.stock_processing.contracts import INTERNAL_ARTICLE_COLUMN

def _resolve_pricing_columns(dataframe: pd.DataFrame, pricing_config: dict) -> tuple[str, str, str]:
    """Require the selected profile columns, including explicit per-run overrides."""
    configured = pricing_config.get("columns", {})
    missing = {field: name for field, name in configured.items() if name and name not in dataframe.columns}
    if missing:
        raise ValueError(f"Configured price-list columns are absent: {missing}.")
    return configured["article"], configured.get("database", ""), configured["price"]


def process_pricing(file_path, pricing_config=None, on_notice=None):
    """Load and pivot one price list into the Stock pipeline's private article key."""
    if not file_path or not os.path.exists(file_path):
        raise FileNotFoundError(f"Required price list is missing: {file_path}")

    try:
        pricing_config = pricing_config or {}
        dataframe = read_table(
            file_path, text=[pricing_config.get("columns", {}).get("article", "")], on_notice=on_notice)
        log_debug_event(
            "pricing_loaded",
            file_path=file_path,
            shape=dataframe.shape,
            columns=list(dataframe.columns),
        )
        article_column, database_column, value_column = _resolve_pricing_columns(
            dataframe,
            pricing_config,
        )
        if not database_column:
            default_store = pricing_config.get("default_store", "")
            if not default_store:
                raise ValueError("A price list without an origin column needs a configured default store.")
            database_column = "__itk_price_origin"
            dataframe[database_column] = default_store
        dataframe[database_column] = dataframe[database_column].astype(str).str.strip().replace(pricing_config.get("aliases", {}))

        article_values = normalize_article_codes(dataframe[article_column])
        if pricing_config.get("article_tokenization", "first_token") == "first_token":
            article_values = article_values.str.split().str[0].fillna("")
        dataframe[INTERNAL_ARTICLE_COLUMN] = article_values
        dataframe = dataframe[article_values.ne("")].copy()
        log_debug_event(
            "pricing_columns_resolved",
            file_path=file_path,
            article_column=article_column,
            database_column=database_column,
            value_column=value_column,
        )
        values, ambiguous = parse_numbers(dataframe[value_column])
        written = dataframe[value_column].notna() & dataframe[value_column].astype(str).str.strip().ne("")
        if values.isna().any():
            rows = [int(label) + 2 for label in values.index[values.isna()][:20]]
            raise ValueError(f"unreadable prices in column '{value_column}' at rows {rows}")
        if on_notice:
            on_notice(describe_unclear_numbers(value_column, ambiguous, "prices"))
        # A blank price is a missing price, not a price of zero.
        dataframe[value_column] = values.where(written)
        if on_notice:
            distinct = dataframe.groupby([INTERNAL_ARTICLE_COLUMN, database_column])[value_column].nunique()
            conflicting = distinct[distinct.gt(1)].index.get_level_values(0).unique()
            if len(conflicting):
                preview = ", ".join(map(str, conflicting[:10])) + ("..." if len(conflicting) > 10 else "")
                on_notice(
                    f"'{os.path.basename(file_path)}': {len(conflicting)} products have more than one "
                    f"price for the same store ({preview}); their average is used.")
        pivot = pd.pivot_table(
            dataframe,
            index=INTERNAL_ARTICLE_COLUMN,
            columns=database_column,
            values=value_column,
            aggfunc="mean",
        ).reset_index()
        pivot.columns.name = None
        log_debug_event(
            "pricing_pivot_ready",
            file_path=file_path,
            shape=pivot.shape,
            columns=list(pivot.columns),
        )
        return pivot
    except Exception as exc:
        log_exception("Processing %s: %s", file_path, exc)
        raise ValueError(f"Could not process required price list {file_path!r}: {exc}") from exc
