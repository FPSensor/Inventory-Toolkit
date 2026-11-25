"""Price attachment and inventory valuation for Stock Processing."""

from __future__ import annotations

import numpy as np
import pandas as pd

from core.business_schema import (
    COST_COLUMN,
    SALES_VALUE_LABEL,
    UNIT_COST_PREFIX,
    UNIT_SALES_PREFIX,
)
from engine.stock_processing.pricing import VARIANT_KEY_PREFIX
from engine.stock_processing.contracts import INTERNAL_ARTICLE_COLUMN, INTERNAL_FAMILY_COLUMN, StockProcessingPlan


def _merge_price_table(
    stock_frame: pd.DataFrame,
    price_frame: pd.DataFrame | None,
    *,
    prefix: str,
) -> tuple[pd.DataFrame, np.ndarray]:
    """Attach one list's unit prices; mark the variant rows priced by product."""
    none = np.zeros(len(stock_frame), dtype=bool)
    if price_frame is None:
        return stock_frame, none

    keys = [column for column in price_frame.columns if column.startswith(VARIANT_KEY_PREFIX)]
    stores = [column for column in price_frame.columns if column != INTERNAL_ARTICLE_COLUMN and column not in keys]
    renames = {store: f"{prefix}{store}" for store in stores}
    if not keys:
        prepared = price_frame.rename(columns=renames)
        return pd.merge(stock_frame, prepared, on=INTERNAL_ARTICLE_COLUMN, how="left"), none

    # A variant's own price wins. Otherwise the product price applies: the rows
    # without variant, or the average of its variants when there are none.
    is_variant = price_frame[keys].ne("").any(axis=1)
    variants = price_frame[is_variant].rename(columns=renames)
    whole = price_frame[~is_variant].groupby(INTERNAL_ARTICLE_COLUMN)[stores].mean()
    fallback = whole.combine_first(price_frame.groupby(INTERNAL_ARTICLE_COLUMN)[stores].mean())
    result = pd.merge(stock_frame, variants, on=[INTERNAL_ARTICLE_COLUMN, *keys], how="left")
    product = fallback.rename(columns=renames).reindex(result[INTERNAL_ARTICLE_COLUMN]).set_axis(result.index)
    columns = list(renames.values())
    by_product = result[keys].ne("").any(axis=1) & result[columns].isna().all(axis=1) & product.notna().any(axis=1)
    result[columns] = result[columns].fillna(product)
    return result, by_product.to_numpy()


def attach_unit_prices(
    stock_frame: pd.DataFrame,
    cost_frame: pd.DataFrame | None,
    sales_frame: pd.DataFrame | None,
    stocked: pd.Series | None = None,
) -> tuple[pd.DataFrame, list[str], list[str]]:
    """Attach cost/sales unit prices and normalize missing values.

    ``stocked`` marks the rows with stock, the only ones worth a warning.
    """
    stocked = np.ones(len(stock_frame), dtype=bool) if stocked is None else stocked.to_numpy()
    result, cost_fallbacks = _merge_price_table(stock_frame, cost_frame, prefix=UNIT_COST_PREFIX)
    result, sales_fallbacks = _merge_price_table(result, sales_frame, prefix=UNIT_SALES_PREFIX)

    unit_price_columns = [
        column
        for column in result.columns
        if column.startswith((UNIT_COST_PREFIX, UNIT_SALES_PREFIX))
    ]
    if unit_price_columns:
        result[unit_price_columns] = result[unit_price_columns].fillna(-1).astype(float)
    notes = [
        f"{count} stock rows have no {label} price for their variant; the product price is used."
        for count, label in (
            (int((cost_fallbacks & stocked).sum()), "cost"), (int((sales_fallbacks & stocked).sum()), "sales"))
        if count
    ]
    return result, unit_price_columns, notes


def missing_price_warnings(stock_frame: pd.DataFrame, plan: StockProcessingPlan) -> list[str]:
    """Name the stocked products that a store values at 0 for lack of a price."""
    messages = []
    for prefix, label in ((UNIT_COST_PREFIX, "cost"), (UNIT_SALES_PREFIX, "sales")):
        # Hidden families stay out of the report, so their prices do not matter.
        reported = ~stock_frame[INTERNAL_FAMILY_COLUMN].isin(plan.hidden_families)
        unpriced = pd.Series(False, index=stock_frame.index)
        units = 0.0
        for store in plan.active_stores:
            if store in plan.regional_groups or store not in stock_frame.columns:
                continue
            price_column = f"{prefix}{store}"
            prices = stock_frame[price_column] if price_column in stock_frame.columns else -1
            missing = reported & stock_frame[store].ne(0) & (prices <= 0)
            units += float(stock_frame.loc[missing, store].sum())
            unpriced |= missing
        products = stock_frame.loc[unpriced, INTERNAL_ARTICLE_COLUMN].drop_duplicates()
        if len(products):
            preview = ", ".join(map(str, products.head(10))) + ("..." if len(products) > 10 else "")
            messages.append(
                f"{len(products)} products with stock have no {label} price in at least one store, "
                f"so {units:,.6g} units are valued at 0: {preview}.")
    return messages


def calculate_inventory_values(
    stock_frame: pd.DataFrame,
    plan: StockProcessingPlan,
) -> pd.DataFrame:
    """Calculate values with the historical entity-order semantics preserved."""
    result = stock_frame.copy()

    # Preserve the original Stock Processing contract exactly: active stores are
    # visited first, regional groups second, and a name configured as a regional
    # group is always evaluated as a group even if it also appears in ``active``.
    for entity in plan.entities_to_value:
        cost_value_column = f"{entity}.{COST_COLUMN}"
        sales_value_column = f"{entity}.{SALES_VALUE_LABEL}"

        if entity in plan.regional_groups:
            branches = plan.regional_groups[entity]
            result[cost_value_column] = sum(
                result.get(f"{branch}.{COST_COLUMN}", 0) for branch in branches
            )
            result[sales_value_column] = sum(
                result.get(f"{branch}.{SALES_VALUE_LABEL}", 0) for branch in branches
            )
            continue

        if entity not in result.columns:
            continue

        unit_cost_column = f"{UNIT_COST_PREFIX}{entity}"
        unit_sales_column = f"{UNIT_SALES_PREFIX}{entity}"
        result[cost_value_column] = np.where(
            result.get(unit_cost_column, 0) <= 0,
            0,
            result.get(unit_cost_column, 0) * result[entity],
        )
        result[sales_value_column] = np.where(
            result.get(unit_sales_column, 0) <= 0,
            0,
            result.get(unit_sales_column, 0) * result[entity],
        )

    return result
