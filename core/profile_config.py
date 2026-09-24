"""Current Inventory Toolkit profile configuration schema and helpers.

Historical profile decoding lives in ``core.legacy_profile_migration`` so the
current configuration model stays free of pre-v3 serialized vocabulary.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Tuple

from core.business_schema import (
    ARTICLE_COLUMN,
    DATABASE_ORIGIN_COLUMN,
    DEFAULT_FAMILY,
    FAMILY_COLUMN,
    PRICE_COLUMN,
    QUANTITY_COLUMN,
    RAW_DATA_SHEET,
    REVIEW_FAMILY,
    SIZE_COLUMN,
)

CONFIG_VERSION = 3

DEFAULTS: Dict[str, dict] = {
    "general/catalog": {
        "version": CONFIG_VERSION,
        "columns": {"article": ARTICLE_COLUMN, "family": FAMILY_COLUMN},
        "default_family": DEFAULT_FAMILY,
    },
    "general/families": {
        "version": CONFIG_VERSION,
        "rules": {REVIEW_FAMILY: [REVIEW_FAMILY, REVIEW_FAMILY.lower()]},
    },
    "general/network": {
        "version": CONFIG_VERSION,
        "active": [],
        "regional_groups": {},
        "stock_database_columns": {},
    },
    "stock_processing/settings": {
        "version": CONFIG_VERSION,
        "cleaning": {
            "text_columns": [ARTICLE_COLUMN],
            "drop_columns": [],
            "numeric_columns": [],
        },
        "pricing": {
            "columns": {
                "article": ARTICLE_COLUMN,
                "database": DATABASE_ORIGIN_COLUMN,
                "price": PRICE_COLUMN,
            },
            "aliases": {DATABASE_ORIGIN_COLUMN: "Base"},
        },
        "output": {
            "raw_data_sheet": RAW_DATA_SHEET,
            "base_columns": [ARTICLE_COLUMN, FAMILY_COLUMN],
            "summaries": [],
        },
    },
    "cross_check/settings": {
        "version": CONFIG_VERSION,
        "filters": {
            "ignored_articles": [],
            "ignored_terms": ["Total general"],
        },
        "price_lists": {
            "cost": {"article_column": ARTICLE_COLUMN, "price_column": PRICE_COLUMN},
            "sales": {"article_column": ARTICLE_COLUMN, "price_column": PRICE_COLUMN},
        },
    },
    "yoy_reports/settings": {
        "version": CONFIG_VERSION,
        "input": {
            "date_column": "Fecha",
            "quantity_column": QUANTITY_COLUMN,
            "grouping_column": FAMILY_COLUMN,
            "item_column": "Articulo",
            "branch_column": "Base",
            "size_column": SIZE_COLUMN,
        },
        "output": {
            "default_path": "analysis_report.xlsx",
            "metrics": ["units", "sales"],
            "annual_comparison": True,
            "include_sizes": False,
        },
        "groups": {},
    },
}


def config_path(configs_dir: Path, logical_name: str) -> Path:
    return configs_dir / f"{logical_name}.json"


def _read(path: Path, default: Any = None) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        return deepcopy(default)


def _write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, indent=4, ensure_ascii=False)
        handle.write("\n")


def initialize_profile_config(configs_dir: Path) -> None:
    """Create missing current-schema files without overwriting user values."""
    for logical_name, default in DEFAULTS.items():
        path = config_path(configs_dir, logical_name)
        if not path.exists():
            _write(path, deepcopy(default))


def ensure_profile_config(configs_dir: Path) -> None:
    """Ensure a profile can be consumed through the current schema."""
    # BEGIN LEGACY_COMPATIBILITY
    from core.legacy_profile_migration import prepare_profile_compatibility

    prepare_profile_compatibility(configs_dir)
    # END LEGACY_COMPATIBILITY
    initialize_profile_config(configs_dir)


def profile_readiness(configs_dir: Path) -> Dict[str, Tuple[bool, str]]:
    """Return human-readable readiness for the Config Hub and setup wizard."""
    ensure_profile_config(configs_dir)
    catalog = _read(config_path(configs_dir, "general/catalog"), {}) or {}
    families = _read(config_path(configs_dir, "general/families"), {}) or {}
    network = _read(config_path(configs_dir, "general/network"), {}) or {}
    stock = _read(config_path(configs_dir, "stock_processing/settings"), {}) or {}
    cross_check = _read(config_path(configs_dir, "cross_check/settings"), {}) or {}
    yoy = _read(config_path(configs_dir, "yoy_reports/settings"), {}) or {}

    columns = catalog.get("columns", {})
    family_rules = families.get("rules", {})
    active_stores = network.get("active", [])
    pricing_columns = stock.get("pricing", {}).get("columns", {})
    price_lists = cross_check.get("price_lists", {})
    yoy_input = yoy.get("input", {})

    return {
        "catalog": (
            bool(columns.get("article") and columns.get("family") and family_rules),
            f"{len(family_rules)} families",
        ),
        "stores": (bool(active_stores), f"{len(active_stores)} active stores"),
        "stock": (
            all(pricing_columns.get(key) for key in ("article", "database", "price")),
            f"{len(stock.get('cleaning', {}).get('drop_columns', []))} drop rules",
        ),
        "cross_check": (
            all(
                price_lists.get(side, {}).get("article_column")
                and price_lists.get(side, {}).get("price_column")
                for side in ("cost", "sales")
            ),
            f"{len(cross_check.get('filters', {}).get('ignored_articles', []))} ignored articles",
        ),
        "yoy": (
            all(
                yoy_input.get(key)
                for key in (
                    "date_column",
                    "quantity_column",
                    "grouping_column",
                    "item_column",
                    "branch_column",
                )
            ),
            f"{len(yoy.get('groups', {}))} report groups",
        ),
    }
