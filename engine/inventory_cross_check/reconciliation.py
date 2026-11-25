"""Match counted articles with system stock and value the differences."""

from __future__ import annotations

from dataclasses import dataclass

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
    REVIEW_PREFIX,
    SALES_TOTAL_COLUMN,
    SYSTEM_STOCK_COLUMN,
)
from engine.inventory_cross_check.data_processor import (
    SCAN_COUNT_COLUMN,
    SCAN_READING_COLUMN,
    calculate_difference,
    normalize_article,
)
from engine.shared.families import assign_families

_OUTPUT_COLUMNS = [
    FAMILY_COLUMN, ARTICLE_COLUMN, SYSTEM_STOCK_COLUMN, PHYSICAL_COUNT_COLUMN,
    DIFFERENCE_COLUMN, COST_TOTAL_COLUMN, SALES_TOTAL_COLUMN,
]


@dataclass
class Reconciliation:
    report: pd.DataFrame
    catalog_articles: int
    readings_to_review: int
    filtered_articles: int


def reconcile(inputs, plan, *, consolidate: bool, partial: bool) -> Reconciliation:
    catalog = [article for article in inputs.system[ARTICLE_COLUMN].unique().tolist() if article]
    families = _source_families(inputs.system, plan)
    counts = _match_readings(inputs.counts, catalog, plan)
    rows = _merge_counts(inputs.system, counts, consolidate=consolidate, partial=partial)
    kept = _apply_filters(rows, plan)
    kept[DIFFERENCE_COLUMN] = [
        calculate_difference(system, counted, ignore_negative_system_stock_when_counted=plan.ignore_negative_stock)
        for system, counted in zip(kept[SYSTEM_STOCK_COLUMN], kept[PHYSICAL_COUNT_COLUMN])
    ]
    kept[FAMILY_COLUMN] = _classify(kept[ARTICLE_COLUMN], families, plan)
    return Reconciliation(
        report=_value_differences(kept, inputs, plan),
        catalog_articles=len(catalog),
        readings_to_review=int(counts[ARTICLE_COLUMN].astype(str).str.startswith(REVIEW_PREFIX).sum()),
        filtered_articles=len(rows) - len(kept),
    )


def _source_families(system, plan):
    if plan.family_mode != "column":
        return {}
    source = plan.system_family
    if source in {plan.system_article, plan.system_quantity}:
        raise ValueError("System product, quantity and category columns must be distinct.")
    categories = system[[ARTICLE_COLUMN, source]].copy()
    categories[source] = (
        categories[source].fillna(plan.default_family).astype(str).str.strip().replace("", plan.default_family))
    if categories.groupby(ARTICLE_COLUMN)[source].nunique().gt(1).any():
        raise ValueError(
            "System stock assigns different categories to the same product. "
            "Resolve those source categories before reconciliation.")
    return categories.drop_duplicates(ARTICLE_COLUMN).set_index(ARTICLE_COLUMN)[source].to_dict()


def _match_readings(counts, catalog, plan):
    lookup = {str(article).upper().strip(): article for article in catalog}
    known = set(lookup)
    if plan.exact_matching:
        def match(reading):
            return lookup.get(str(reading).upper().strip(), f"{REVIEW_PREFIX}{reading}")
    else:
        def match(reading):
            return normalize_article(reading, catalog, known)
    counts = counts.copy()
    counts[ARTICLE_COLUMN] = counts[SCAN_READING_COLUMN].apply(match)
    return counts


def _merge_counts(system, counts, *, consolidate, partial):
    if consolidate:
        stock = system.groupby(ARTICLE_COLUMN, as_index=False)[QUANTITY_COLUMN].sum()
    else:
        stock = system[[ARTICLE_COLUMN, QUANTITY_COLUMN]]
    counted = counts.groupby(ARTICLE_COLUMN, as_index=False)[SCAN_COUNT_COLUMN].sum()
    return pd.merge(
        counted.rename(columns={SCAN_COUNT_COLUMN: PHYSICAL_COUNT_COLUMN}),
        stock.rename(columns={QUANTITY_COLUMN: SYSTEM_STOCK_COLUMN}),
        on=ARTICLE_COLUMN,
        how="left" if partial else "outer",
    ).fillna(0)


def _apply_filters(rows, plan):
    rows = rows[~rows[ARTICLE_COLUMN].isin(plan.ignored_articles)]
    for term in plan.ignored_terms:
        rows = rows[~rows[ARTICLE_COLUMN].astype(str).str.contains(term, case=False, na=False, regex=False)]
    return rows.copy()


def _classify(articles, source_families, plan):
    if plan.family_mode == "column":
        return articles.map(source_families).fillna(plan.default_family)
    if plan.family_mode == "none":
        return plan.default_family
    return assign_families(articles, plan.family_rules, default_family=plan.default_family)


def _value_differences(rows, inputs, plan):
    costs = inputs.costs.groupby(ARTICLE_COLUMN, as_index=False)[COST_COLUMN].mean()
    sales = inputs.sales.groupby(ARTICLE_COLUMN, as_index=False)[PRICE_COLUMN].mean()
    report = rows.merge(costs, on=ARTICLE_COLUMN, how="left").merge(sales, on=ARTICLE_COLUMN, how="left")
    report[COST_TOTAL_COLUMN] = report[DIFFERENCE_COLUMN] * report[COST_COLUMN].fillna(0)
    report[SALES_TOTAL_COLUMN] = report[DIFFERENCE_COLUMN] * report[PRICE_COLUMN].fillna(0)
    report = report[report[DIFFERENCE_COLUMN].abs() > plan.tolerance]
    report = report[_OUTPUT_COLUMNS].sort_values(by=[FAMILY_COLUMN, ARTICLE_COLUMN])
    return report.rename(columns={FAMILY_COLUMN: plan.family_label, ARTICLE_COLUMN: plan.article_label})
