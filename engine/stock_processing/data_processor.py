"""Pure dataframe transformations for the Stock Processing workflow."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from core.business_schema import COST_COLUMN, SALES_VALUE_LABEL
from core.logger import log_debug_event
from engine.shared.families import assign_families
from engine.stock_processing.contracts import (
    INTERNAL_ARTICLE_COLUMN,
    INTERNAL_FAMILY_COLUMN,
    StockProcessingPlan,
)


def _normalize_text(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip()


def _normalize_numeric(series: pd.Series) -> pd.Series:
    normalized = series.astype(str).str.replace(",", ".", regex=False).str.strip()
    numeric = pd.to_numeric(normalized, errors="coerce").fillna(0)
    # Keep exact whole quantities integral without truncating measured quantities.
    bounds = np.iinfo(np.int64)
    if np.isfinite(numeric).all() and numeric.between(bounds.min, bounds.max).all() and numeric.mod(1).eq(0).all():
        return numeric.astype(np.int64)
    return numeric


def adapt_stock_headers(raw_frame, plan, source_article):
    """Resolve explicit headers once; never silently fall back to an output label."""
    if plan.input.get("format") == "long":
        quantity = plan.input["quantity_column"]
        branch = plan.input["branch_column"]
        needed = [source_article, quantity] + ([branch] if branch else [])
        if not quantity or len(set(needed)) != len(needed) or any(column not in raw_frame.columns for column in needed):
            raise ValueError("Long stock requires distinct configured product, quantity and optional location columns.")
        frame = raw_frame.copy()
        locations = frame[branch].fillna("").astype(str).str.strip() if branch else pd.Series(plan.input["default_store"], index=frame.index)
        unknown = ~locations.isin(plan.active_stores)
        if unknown.any():
            rows = [int(position) + 2 for position in np.flatnonzero(unknown.to_numpy())[:20]]
            raise ValueError(f"Stock has unknown or missing locations at Excel rows {rows}.")
        amounts = pd.to_numeric(frame[quantity].astype(str).str.replace(",", ".", regex=False), errors="coerce")
        if not np.isfinite(amounts).all():
            raise ValueError("Long stock contains missing or invalid numeric quantities.")
        if source_article != plan.article_column and plan.article_column in frame.columns:
            raise ValueError("Stock product mapping collides with an existing output column.")
        frame = frame.rename(columns={source_article: plan.article_column})
        for store in plan.active_stores:
            if store in frame.columns:
                raise ValueError(f"Stock location label {store!r} collides with an input column.")
            frame[store] = amounts.where(locations.eq(store), 0)
        return frame
    mappings = [(source_article, plan.article_column), *
        ((header, store) for store, header in plan.input["quantity_columns"].items())]
    sources = [source for source, _ in mappings]
    if len(set(sources)) != len(sources):
        raise ValueError("Article and store quantities must use distinct input columns.")
    missing = [source for source in sources if source not in raw_frame.columns]
    if missing:
        raise ValueError(f"Stock input is missing configured columns: {missing}")
    renames = dict(mappings)
    if any(target in raw_frame.columns and target not in renames for source, target in mappings if source != target):
        raise ValueError("Stock input mapping collides with another existing column.")
    return raw_frame.rename(columns=renames)


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
    if plan.input.get("family_mode", "rules") == "column":
        source = plan.input["family_column"]
        if not source or source not in raw_frame.columns or source in plan.drop_columns:
            raise ValueError("Choose an existing category column and keep it in stock cleaning.")
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

    for column in dict.fromkeys((*plan.numeric_columns, *plan.active_stores, *plan.stock_database_columns.values())):
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


def remove_unidentified_stock(raw_frame: pd.DataFrame, plan: StockProcessingPlan) -> tuple[pd.DataFrame, str | None]:
    """Omit unidentified rows, reporting quantities that require source review."""
    if plan.article_column not in raw_frame.columns:
        return raw_frame, None  # prepare_stock_frame reports the missing column.
    missing = raw_frame[plan.article_column].isna() | raw_frame[plan.article_column].astype(str).str.strip().eq("")
    if not missing.any():
        return raw_frame, None
    quantities = [col for col in (*plan.active_stores, *plan.stock_database_columns.values()) if col in raw_frame.columns]
    with_quantity = pd.Series(False, index=raw_frame.index)
    row_totals = pd.Series(0.0, index=raw_frame.index)
    if quantities:
        numeric = raw_frame[quantities].apply(pd.to_numeric, errors="coerce").fillna(0)
        with_quantity = numeric.ne(0).any(axis=1)
        row_totals = numeric.sum(axis=1)
    affected = raw_frame.index[missing & with_quantity]
    warning = None
    if len(affected):
        rows = [int(raw_frame.index.get_loc(idx)) + 2 for idx in affected]
        preview = ", ".join(
            f"{number} ({row_totals.loc[idx]:g} units)"
            for number, idx in zip(rows[:20], affected[:20])
        ) + ("..." if len(rows) > 20 else "")
        warning = (
            f"{len(rows)} stock rows with quantities but no article were excluded "
            f"({row_totals.loc[affected].sum():g} net units). "
            f"Source Excel rows: {preview}. Review the original file."
        )
    return raw_frame.loc[~missing].copy(), warning


def validate_stock_network(frame: pd.DataFrame, plan: StockProcessingPlan) -> None:
    missing_stores = [store for store in plan.active_stores if store not in frame.columns]
    missing_deposits = [col for col in plan.stock_database_columns.values() if col not in frame.columns]
    absent_branches = [branch for branches in plan.regional_groups.values() for branch in branches if branch not in plan.active_stores]
    if missing_stores or missing_deposits or absent_branches:
        raise ValueError(
            "Stock network columns/groups are incomplete: "
            f"missing stores={missing_stores}, missing deposits={missing_deposits}, "
            f"unknown regional members={absent_branches}"
        )


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
    source_column=None,
    use_rules=True,
) -> pd.DataFrame:
    """Attach the private family key using the shared longest-prefix classifier."""
    result = frame.copy()
    if source_column:
        result[INTERNAL_FAMILY_COLUMN] = result[source_column].fillna(default_family).astype(str).str.strip().replace("", default_family)
    elif use_rules:
        result[INTERNAL_FAMILY_COLUMN] = assign_families(
            result[INTERNAL_ARTICLE_COLUMN], family_rules, default_family=default_family)
    else:
        result[INTERNAL_FAMILY_COLUMN] = default_family
    family_counts = result[INTERNAL_FAMILY_COLUMN].value_counts(dropna=False)
    log_debug_event(
        "stock_processing_family_assignment",
        row_count=len(result),
        family_count=int(result[INTERNAL_FAMILY_COLUMN].nunique(dropna=False)),
        unmatched_rows=int(family_counts.get(default_family, 0)),
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
