"""Resolved profile contract for Cross Check."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from core.business_schema import ARTICLE_COLUMN, PRICE_COLUMN
from core.config.configuration_manager import ConfigurationManager
from engine.shared.families import build_family_rules


@dataclass(frozen=True)
class CrossCheckPlan:
    """Headers to read, reconciliation rules and report labels for one run."""

    article_label: str
    family_label: str
    default_family: str
    family_rules: Any
    family_mode: str
    system_article: str
    system_quantity: str
    system_family: str
    system_store: str
    store_of_database: Mapping[str, str]
    count_settings: Mapping[str, Any]
    count_columns: Mapping[str, str] | None
    cost_columns: tuple[str, str, str]
    sales_columns: tuple[str, str, str]
    exact_matching: bool
    first_token_prices: bool
    ignored_articles: tuple[str, ...]
    ignored_terms: tuple[str, ...]
    ignore_negative_stock: bool
    tolerance: float

    @classmethod
    def from_manager(cls, config: ConfigurationManager, overrides: Mapping[str, Any]) -> "CrossCheckPlan":
        settings, labels = config.get_cross_check_config(), config.get_catalog_columns()
        source, filters = settings["input"], settings["filters"]
        system = overrides.get("system", {})

        def prices(side):
            columns = overrides.get(side, settings["price_lists"].get(side, {}))
            configured = settings["price_lists"].get(side, {})
            return (columns.get("article_column", ARTICLE_COLUMN), columns.get("price_column", PRICE_COLUMN),
                    columns.get("store_column", configured.get("store_column", "")))

        return cls(
            article_label=labels["article"],
            family_label=labels["family"],
            default_family=config.get_default_family(),
            family_rules=build_family_rules(config.get_family_rules()),
            family_mode=source["family_mode"],
            system_article=system.get("article", source["article_column"] or labels["article"]),
            system_quantity=system.get("quantity", source["quantity_column"]),
            system_family=system.get("family", source["family_column"]),
            system_store=system.get("store", source["store_column"]),
            # A deposit's stock belongs to the store it supplies.
            store_of_database={
                deposit: store for store, deposit in config.get_network_config()["stock_database_columns"].items()},
            count_settings=source,
            count_columns=overrides.get("count"),
            cost_columns=prices("cost"),
            sales_columns=prices("sales"),
            exact_matching=source["matching"] == "exact",
            first_token_prices=settings["pricing"]["article_tokenization"] == "first_token",
            ignored_articles=tuple(filters.get("ignored_articles", [])),
            ignored_terms=tuple(filters.get("ignored_terms", [])),
            ignore_negative_stock=settings["reconciliation"]["ignore_negative_system_stock_when_counted"],
            tolerance=settings["reconciliation"]["quantity_tolerance"],
        )
