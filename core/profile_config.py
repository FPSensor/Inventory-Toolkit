"""Profile configuration defaults, upgrades, and legacy migration.

The current layout is module-oriented: each feature owns one cohesive settings
file instead of scattering related keys across unrelated JSON files.
"""

from __future__ import annotations

import json
import shutil
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

# Legacy v1 paths and keys are intentionally preserved here because migration
# must be able to read profiles created before the English configuration model.
LEGACY_FILES = (
    "general/settings.json",
    "general/databases.json",
    "general/stores.json",
    "general/familias.json",
    "general/schema.json",
    "stock_processing/cleaning.json",
    "stock_processing/pricing.json",
    "cross_check/cross_check_settings.json",
    "yoy_reports/reports.json",
)


def config_path(configs_dir: Path, logical_name: str) -> Path:
    return configs_dir / f"{logical_name}.json"


def _read(path: Path, default: Any = None) -> Any:
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return deepcopy(default)


def _write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, indent=4, ensure_ascii=False)
        fh.write("\n")


def initialize_profile_config(configs_dir: Path) -> None:
    """Create missing current-schema files without overwriting user values."""
    for logical_name, default in DEFAULTS.items():
        path = config_path(configs_dir, logical_name)
        if not path.exists():
            _write(path, deepcopy(default))


def has_legacy_config(configs_dir: Path) -> bool:
    return any((configs_dir / relative_path).exists() for relative_path in LEGACY_FILES)


def has_modular_config(configs_dir: Path) -> bool:
    return any(config_path(configs_dir, name).exists() for name in DEFAULTS)


def _upgrade_summary(summary: dict) -> dict:
    """Convert pre-v3 stock summary structure to English schema keys."""
    upgraded = dict(summary)
    if "sheet_name" not in upgraded and "nombre_hoja" in upgraded:
        upgraded["sheet_name"] = upgraded.pop("nombre_hoja")
    if "entities" not in upgraded and "locales_a_incluir" in upgraded:
        upgraded["entities"] = upgraded.pop("locales_a_incluir")
    if "titles" not in upgraded and "titulos" in upgraded:
        upgraded["titles"] = upgraded.pop("titulos")
    return upgraded


def upgrade_profile_config(configs_dir: Path) -> bool:
    """Upgrade modular profile files in place to the current schema version."""
    changed = False
    for logical_name, default in DEFAULTS.items():
        path = config_path(configs_dir, logical_name)
        if not path.exists():
            continue
        data = _read(path, deepcopy(default)) or deepcopy(default)
        original = deepcopy(data)

        if logical_name == "stock_processing/settings":
            output = data.setdefault("output", {})
            output["summaries"] = [
                _upgrade_summary(summary) for summary in output.get("summaries", [])
            ]
        elif logical_name == "yoy_reports/settings":
            output = data.setdefault("output", {})
            metric_map = {"unidades": "units", "ventas": "sales"}
            output["metrics"] = [metric_map.get(metric, metric) for metric in output.get("metrics", [])]

        data["version"] = CONFIG_VERSION
        if data != original:
            _write(path, data)
            changed = True
    return changed


def ensure_profile_config(configs_dir: Path) -> None:
    """Ensure a profile exists in the current modular configuration schema."""
    if has_legacy_config(configs_dir) and not has_modular_config(configs_dir):
        migrate_legacy_config(configs_dir, remove_legacy=False)
    initialize_profile_config(configs_dir)
    upgrade_profile_config(configs_dir)


def migrate_legacy_config(configs_dir: Path, *, remove_legacy: bool = False) -> bool:
    """Migrate the old mixed v1 layout into the current module-oriented layout.

    Existing modular files win. Legacy files only populate missing files, so
    rerunning migration is safe. When ``remove_legacy`` is true, source files
    are archived under ``configs/_legacy_v1_backup`` after conversion.
    """
    if not has_legacy_config(configs_dir):
        initialize_profile_config(configs_dir)
        upgrade_profile_config(configs_dir)
        return False

    old_settings = _read(configs_dir / "general/settings.json", {}) or {}
    old_families = _read(configs_dir / "general/familias.json", {}) or {}
    old_stores = _read(configs_dir / "general/stores.json", {}) or {}
    old_databases = _read(configs_dir / "general/databases.json", {}) or {}
    old_cleaning = _read(configs_dir / "stock_processing/cleaning.json", {}) or {}
    old_pricing = _read(configs_dir / "stock_processing/pricing.json", {}) or {}
    old_cross_check = _read(configs_dir / "cross_check/cross_check_settings.json", {}) or {}
    old_reports = _read(configs_dir / "yoy_reports/reports.json", {}) or {}

    migrated = {
        "general/catalog": {
            "version": CONFIG_VERSION,
            "columns": {
                "article": old_settings.get("columna_articulo", ARTICLE_COLUMN),
                "family": old_settings.get("columna_familia", FAMILY_COLUMN),
            },
            "default_family": old_settings.get("familia_por_defecto", DEFAULT_FAMILY),
        },
        "general/families": {
            "version": CONFIG_VERSION,
            "rules": old_families or deepcopy(DEFAULTS["general/families"]["rules"]),
        },
        "general/network": {
            "version": CONFIG_VERSION,
            "active": old_stores.get("locales_activos", []),
            "regional_groups": old_stores.get("grupos_regionales", {}),
            "stock_database_columns": old_databases,
        },
        "stock_processing/settings": {
            "version": CONFIG_VERSION,
            "cleaning": {
                "text_columns": old_cleaning.get("columnas_texto_a_limpiar", [ARTICLE_COLUMN]),
                "drop_columns": old_cleaning.get("columnas_a_eliminar", []),
                "numeric_columns": old_cleaning.get("columnas_a_formatear", []),
            },
            "pricing": {
                "columns": _legacy_pricing_columns(old_pricing),
                "aliases": old_pricing.get("mapeo_nombres", {}),
            },
            "output": {
                "raw_data_sheet": old_reports.get("hoja_datos_crudos", RAW_DATA_SHEET),
                "base_columns": old_reports.get("orden_columnas_base", [ARTICLE_COLUMN, FAMILY_COLUMN]),
                "summaries": [
                    _upgrade_summary(summary) for summary in old_reports.get("resumenes", [])
                ],
            },
        },
        "cross_check/settings": {
            "version": CONFIG_VERSION,
            "filters": {
                "ignored_articles": old_cross_check.get("articulos_ignorados", []),
                "ignored_terms": old_cross_check.get("palabras_ignoradas", ["Total general"]),
            },
            "price_lists": {
                "cost": _legacy_price_map(old_cross_check.get("columnas_costo", {})),
                "sales": _legacy_price_map(old_cross_check.get("columnas_venta", {})),
            },
        },
        "yoy_reports/settings": {
            "version": CONFIG_VERSION,
            "input": _legacy_yoy_input(old_reports),
            "output": {
                "default_path": old_reports.get("output_path", "analysis_report.xlsx"),
                "metrics": [
                    {"unidades": "units", "ventas": "sales"}.get(metric, metric)
                    for metric in old_reports.get("metricas_salida", ["unidades", "ventas"])
                ],
                "annual_comparison": old_reports.get("comparacion_anual", True),
                "include_sizes": old_reports.get("incluir_talles", False),
            },
            "groups": old_reports.get("report_structures", {}),
        },
    }

    for logical_name, data in migrated.items():
        path = config_path(configs_dir, logical_name)
        if not path.exists():
            _write(path, data)

    if remove_legacy:
        backup_root = configs_dir / "_legacy_v1_backup"
        for relative_path in LEGACY_FILES:
            path = configs_dir / relative_path
            if path.exists():
                target = backup_root / relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(path), str(target))

    upgrade_profile_config(configs_dir)
    return True


def _legacy_pricing_columns(data: dict) -> dict:
    columns = data.get("columnas_esperadas", [])
    return {
        "article": columns[0] if len(columns) > 0 else ARTICLE_COLUMN,
        "database": columns[1] if len(columns) > 1 else DATABASE_ORIGIN_COLUMN,
        "price": columns[2] if len(columns) > 2 else PRICE_COLUMN,
    }


def _legacy_price_map(data: dict) -> dict:
    return {
        "article_column": data.get("articulo", ARTICLE_COLUMN),
        "price_column": data.get("precio", PRICE_COLUMN),
    }


def _legacy_yoy_input(data: dict) -> dict:
    source = data.get("data_source", {})
    return {
        "date_column": source.get("date_column", "Fecha"),
        "quantity_column": source.get("quantity_column", QUANTITY_COLUMN),
        "grouping_column": source.get("grouping_column", FAMILY_COLUMN),
        "item_column": source.get("item_column", "Articulo"),
        "branch_column": source.get("branch_column", "Base"),
        "size_column": source.get("size_column", data.get("columna_talle", SIZE_COLUMN)),
    }


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
