"""Pure dataframe transformations for the Stock Processing workflow."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from core.business_schema import COST_COLUMN, REVIEW_FAMILY, SALES_VALUE_LABEL
from core.logger import log_debug_event
from engine.shared.families import assign_families
from engine.stock_processing.contracts import (
    INTERNAL_ARTICLE_COLUMN,
    INTERNAL_FAMILY_COLUMN,
    StockProcessingPlan,
)


def _normalize_text(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip()


def _normalize_numeric(series: pd.Series) -> pd.Series:
    normalized = series.astype(str).str.replace(",", ".", regex=False).str.strip()
    return pd.to_numeric(normalized, errors="coerce").fillna(0).astype(int)


def prepare_stock_frame(raw_frame: pd.DataFrame, plan: StockProcessingPlan) -> pd.DataFrame:
    """Validate/clean raw stock and establish private canonical catalog keys."""
    if plan.article_column not in raw_frame.columns:
        raise ValueError(
            f"Stock input is missing configured article column '{plan.article_column}'."
        )
    if plan.article_column in plan.drop_columns:
        raise ValueError(
            f"Stock cleaning cannot drop the configured article column '{plan.article_column}'."
        )
    if INTERNAL_ARTICLE_COLUMN in raw_frame.columns or INTERNAL_FAMILY_COLUMN in raw_frame.columns:
        raise ValueError(
            "Stock input contains a reserved Inventory Toolkit internal column name."
        )

    frame = raw_frame.copy()
    dropped_columns = [column for column in plan.drop_columns if column in frame.columns]
    frame = frame.drop(columns=dropped_columns, errors="ignore")

    for column in plan.text_columns:
        if column in frame.columns:
            frame[column] = _normalize_text(frame[column])

    for column in plan.numeric_columns:
        if column in frame.columns:
            frame[column] = _normalize_numeric(frame[column])

    # The article is an identity key, so it is normalized at the boundary even
    # when a profile forgot to repeat it in cleaning.text_columns.
    frame[plan.article_column] = _normalize_text(frame[plan.article_column])
    frame = frame.rename(columns={plan.article_column: INTERNAL_ARTICLE_COLUMN})

    log_debug_event(
        "stock_processing_cleaning_columns",
        dropped_columns=dropped_columns,
        remaining_column_count=len(frame.columns),
        article_input_column=plan.article_column,
        article_internal_column=INTERNAL_ARTICLE_COLUMN,
    )
    return frame


def merge_stock_database_columns(
    frame: pd.DataFrame,
    mappings: Mapping[str, str],
) -> tuple[pd.DataFrame, list[tuple[str, str]]]:
    """Merge configured raw deposit columns into their visible store columns."""
    result = frame.copy()
    merged: list[tuple[str, str]] = []
    for store_column, deposit_column in mappings.items():
        if store_column in result.columns and deposit_column in result.columns:
            result[store_column] = result[store_column] + result[deposit_column]
            result = result.drop(columns=[deposit_column])
            merged.append((store_column, deposit_column))
    return result, merged


def add_regional_groups(
    frame: pd.DataFrame,
    regional_groups: Mapping[str, tuple[str, ...]],
) -> pd.DataFrame:
    """Add configured regional quantity columns without assuming fixed stores."""
    result = frame.copy()
    for group_name, branches in regional_groups.items():
        result[group_name] = sum(result.get(branch, 0) for branch in branches)
    return result


def classify_stock_families(
    frame: pd.DataFrame,
    family_rules,
    *,
    default_family: str,
) -> pd.DataFrame:
    """Attach the private family key using the shared longest-prefix classifier."""
    result = frame.copy()
    result[INTERNAL_FAMILY_COLUMN] = assign_families(
        result[INTERNAL_ARTICLE_COLUMN],
        family_rules,
        default_family=default_family,
    )
    family_counts = result[INTERNAL_FAMILY_COLUMN].value_counts(dropna=False)
    log_debug_event(
        "stock_processing_family_assignment",
        row_count=len(result),
        family_count=int(result[INTERNAL_FAMILY_COLUMN].nunique(dropna=False)),
        review_rows=int(family_counts.get(REVIEW_FAMILY, 0)),
        top_families=family_counts.head(10).to_dict(),
    )
    return result


def project_stock_output(frame: pd.DataFrame, plan: StockProcessingPlan) -> pd.DataFrame:
    """Select the profile-owned final layout and restore catalog-facing labels."""
    final_column_order = [plan.internal_base_column(column) for column in plan.base_columns]
    for entity in plan.entities_to_value:
        final_column_order.extend(
            [entity, f"{entity}.{COST_COLUMN}", f"{entity}.{SALES_VALUE_LABEL}"]
        )

    selected = frame[
        [column for column in final_column_order if column in frame.columns]
    ].copy()
    return plan.expose_catalog_columns(selected)


def calculate_margin(dataframe, sales_column, cost_column):
    return np.where(
        dataframe[sales_column] > 0,
        (dataframe[sales_column] - dataframe[cost_column]) / dataframe[sales_column],
        0,
    )


# Backward-compatible import location retained for v1.x callers.
from engine.stock_processing.pricing import process_pricing  # noqa: E402,F401
