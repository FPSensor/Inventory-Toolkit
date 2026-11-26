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
    STORE_COLUMN,
    build_article_index,
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
    warnings: tuple[str, ...] = ()


def reconcile(inputs, plan, *, partial: bool) -> Reconciliation:
    catalog = inputs.system[ARTICLE_COLUMN].unique().tolist()
    # A counted product may have no row in system stock; the price lists still
    # know it, so its reading is not cut down to a shorter article.
    known = build_article_index([*catalog, *inputs.costs[ARTICLE_COLUMN], *inputs.sales[ARTICLE_COLUMN]])
    families = _source_families(inputs.system, plan)
    counts = _match_readings(inputs.counts, known, plan)
    rows = _merge_counts(inputs.system, counts, partial=partial)
    kept = _apply_filters(rows, plan)
    kept[DIFFERENCE_COLUMN] = [
        calculate_difference(system, counted, ignore_negative_system_stock_when_counted=plan.ignore_negative_stock)
        for system, counted in zip(kept[SYSTEM_STOCK_COLUMN], kept[PHYSICAL_COUNT_COLUMN])
    ]
    kept[FAMILY_COLUMN] = _classify(kept[ARTICLE_COLUMN], families, plan)
    report, warnings = _value_differences(kept, inputs, plan)
    return Reconciliation(
        report=report,
        catalog_articles=len(catalog),
        readings_to_review=int(counts[ARTICLE_COLUMN].astype(str).str.startswith(REVIEW_PREFIX).sum()),
        filtered_articles=len(rows) - len(kept),
        warnings=warnings,
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


def _match_readings(counts, article_index, plan):
    known, _ = article_index
    if plan.exact_matching:
        def match(reading):
            code = str(reading).upper().strip()
            return code if code in known else f"{REVIEW_PREFIX}{reading}"
    else:
        def match(reading):
            return normalize_article(reading, article_index)
    counts = counts.copy()
    counts[ARTICLE_COLUMN] = counts[SCAN_READING_COLUMN].apply(match)
    return counts


def _merge_counts(system, counts, *, partial):
    # Counts carry no store or database, so system stock needs one row per
    # product: joining repeated rows would repeat the whole count on each.
    stock = system.groupby(ARTICLE_COLUMN, as_index=False)[QUANTITY_COLUMN].sum()
    counted = counts.groupby(ARTICLE_COLUMN, as_index=False)[SCAN_COUNT_COLUMN].sum()
    return pd.merge(
        counted.rename(columns={SCAN_COUNT_COLUMN: PHYSICAL_COUNT_COLUMN}),
        stock.rename(columns={QUANTITY_COLUMN: SYSTEM_STOCK_COLUMN}),
        on=ARTICLE_COLUMN,
        how="left" if partial else "outer",
    ).fillna(0)


def _apply_filters(rows, plan):
    ignored = {str(article).strip().upper() for article in plan.ignored_articles}
    rows = rows[~rows[ARTICLE_COLUMN].astype(str).str.upper().isin(ignored)]
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
    stores = _counted_stores(inputs.system, plan)
    differing = rows.loc[rows[DIFFERENCE_COLUMN].abs() > plan.tolerance, ARTICLE_COLUMN]
    costs, cost_notes = _unit_prices(inputs.costs, COST_COLUMN, "cost", stores, differing)
    sales, sales_notes = _unit_prices(inputs.sales, PRICE_COLUMN, "sales", stores, differing)
    report = rows.merge(costs, on=ARTICLE_COLUMN, how="left").merge(sales, on=ARTICLE_COLUMN, how="left")
    report[COST_TOTAL_COLUMN] = report[DIFFERENCE_COLUMN] * report[COST_COLUMN].fillna(0)
    report[SALES_TOTAL_COLUMN] = report[DIFFERENCE_COLUMN] * report[PRICE_COLUMN].fillna(0)
    report = report[report[DIFFERENCE_COLUMN].abs() > plan.tolerance]
    warnings = tuple(filter(None, (
        *cost_notes, *sales_notes,
        _unpriced(report, COST_COLUMN, "cost"), _unpriced(report, PRICE_COLUMN, "sales"))))
    report = report[_OUTPUT_COLUMNS].sort_values(by=[FAMILY_COLUMN, ARTICLE_COLUMN])
    return report.rename(columns={FAMILY_COLUMN: plan.family_label, ARTICLE_COLUMN: plan.article_label}), warnings


def _counted_stores(system, plan):
    """Stores whose stock the count covers; deposits count for their store."""
    if STORE_COLUMN not in system.columns:
        return set()
    return {plan.store_of_database.get(name, name) for name in system[STORE_COLUMN] if name}


def _unit_prices(prices, value_column, label, stores, differing):
    """One unit price per product, taken from the counted store when possible."""
    notes = []
    if STORE_COLUMN in prices.columns:
        if len(stores) == 1:
            store = next(iter(stores))
            selected = prices[prices[STORE_COLUMN].eq(store)]
            if selected.empty:
                raise ValueError(
                    f"The {label} price list has no prices for {store!r}, the store in system stock. "
                    f"Stores in the list: {sorted(prices[STORE_COLUMN].unique())[:20]}.")
            prices = selected
        elif stores:
            notes.append(
                f"System stock covers several stores ({', '.join(sorted(stores))}), so {label} prices "
                "are averaged across the price list.")
        else:
            notes.append(
                f"The {label} price list has prices per store, but system stock has no store column "
                "configured, so prices are averaged across stores.")
    distinct = prices.groupby(ARTICLE_COLUMN)[value_column].nunique()
    conflicting = [article for article in differing if distinct.get(article, 0) > 1]
    if conflicting:
        notes.append(
            f"{len(conflicting)} products with differences have more than one {label} price; their "
            f"average is used: {', '.join(map(str, conflicting[:10]))}{'...' if len(conflicting) > 10 else ''}.")
    return prices.groupby(ARTICLE_COLUMN, as_index=False)[value_column].mean(), notes


def _unpriced(report, price_column, label):
    missing = report[price_column].isna() & ~report[ARTICLE_COLUMN].astype(str).str.startswith(REVIEW_PREFIX)
    if not missing.any():
        return None
    return (
        f"{int(missing.sum())} products with differences have no {label} price, so their "
        f"{label} total is 0: {', '.join(map(str, report.loc[missing, ARTICLE_COLUMN].head(10)))}"
        f"{'...' if missing.sum() > 10 else ''}.")
