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
from engine.stock_processing.contracts import INTERNAL_ARTICLE_COLUMN, StockProcessingPlan


def _merge_price_table(
    stock_frame: pd.DataFrame,
    price_frame: pd.DataFrame | None,
    *,
    prefix: str,
) -> pd.DataFrame:
    if price_frame is None:
        return stock_frame

    renames = {
        column: f"{prefix}{column}"
        for column in price_frame.columns
        if column != INTERNAL_ARTICLE_COLUMN
    }
    prepared = price_frame.rename(columns=renames)
    return pd.merge(stock_frame, prepared, on=INTERNAL_ARTICLE_COLUMN, how="left")


def attach_unit_prices(
    stock_frame: pd.DataFrame,
    cost_frame: pd.DataFrame | None,
    sales_frame: pd.DataFrame | None,
) -> tuple[pd.DataFrame, list[str]]:
    """Attach cost/sales unit prices and normalize missing values."""
    result = _merge_price_table(stock_frame, cost_frame, prefix=UNIT_COST_PREFIX)
    result = _merge_price_table(result, sales_frame, prefix=UNIT_SALES_PREFIX)

    unit_price_columns = [
        column
        for column in result.columns
        if column.startswith((UNIT_COST_PREFIX, UNIT_SALES_PREFIX))
    ]
    if unit_price_columns:
        result[unit_price_columns] = result[unit_price_columns].fillna(-1).astype(float)
    return result, unit_price_columns


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


def remove_unit_prices(stock_frame: pd.DataFrame, unit_price_columns: list[str]) -> pd.DataFrame:
    return stock_frame.drop(columns=unit_price_columns, errors="ignore")
