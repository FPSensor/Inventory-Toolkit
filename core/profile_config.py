"""Profile configuration layout, defaults, validation and legacy migration.

The v2 layout is deliberately module-oriented.  Each feature owns one cohesive
settings file instead of spreading related keys across unrelated JSON files.
"""

from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

CONFIG_VERSION = 2

DEFAULTS: Dict[str, dict] = {
    "general/catalog": {
        "version": CONFIG_VERSION,
        "columns": {"article": "Artículo", "family": "Familias"},
        "default_family": "Otro",
    },
    "general/families": {
        "version": CONFIG_VERSION,
        "rules": {"REVISAR": ["REVISAR", "revisar"]},
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
            "text_columns": ["Artículo"],
            "drop_columns": [],
            "numeric_columns": [],
        },
        "pricing": {
            "columns": {
                "article": "Artículo",
                "database": "Origen - Base de datos",
                "price": "Precio",
            },
            "aliases": {"Origen - Base de datos": "Base"},
        },
        "output": {
            "raw_data_sheet": "Datos",
            "base_columns": ["Artículo", "Familias"],
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
            "cost": {"article_column": "Artículo", "price_column": "Precio"},
            "sales": {"article_column": "Artículo", "price_column": "Precio"},
        },
    },
    "yoy_reports/settings": {
        "version": CONFIG_VERSION,
        "input": {
            "date_column": "Fecha",
            "quantity_column": "Cantidad",
            "grouping_column": "Familias",
            "item_column": "Articulo",
            "branch_column": "Base",
            "size_column": "Talle",
        },
        "output": {
            "default_path": "analysis_report.xlsx",
            "metrics": ["unidades", "ventas"],
            "annual_comparison": True,
            "include_sizes": False,
        },
        "groups": {},
    },
}

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


def initialize_v2_config(configs_dir: Path) -> None:
    """Create missing v2 files without overwriting existing user values."""
    for logical_name, default in DEFAULTS.items():
        path = config_path(configs_dir, logical_name)
        if not path.exists():
            _write(path, deepcopy(default))


def has_legacy_config(configs_dir: Path) -> bool:
    return any((configs_dir / rel).exists() for rel in LEGACY_FILES)


def has_v2_config(configs_dir: Path) -> bool:
    return all(config_path(configs_dir, name).exists() for name in DEFAULTS)


def migrate_legacy_config(configs_dir: Path, *, remove_legacy: bool = False) -> bool:
    """Migrate the old mixed layout into the v2 module-oriented layout.

    Existing v2 files win.  Legacy files are only used to populate missing v2
    files, so rerunning migration is safe.  Returns True when legacy input was
    found and a migration was attempted.
    """
    if not has_legacy_config(configs_dir):
        initialize_v2_config(configs_dir)
        return False

    old_settings = _read(configs_dir / "general/settings.json", {}) or {}
    old_families = _read(configs_dir / "general/familias.json", {}) or {}
    old_stores = _read(configs_dir / "general/stores.json", {}) or {}
    old_databases = _read(configs_dir / "general/databases.json", {}) or {}
    old_cleaning = _read(configs_dir / "stock_processing/cleaning.json", {}) or {}
    old_pricing = _read(configs_dir / "stock_processing/pricing.json", {}) or {}
    old_cross = _read(configs_dir / "cross_check/cross_check_settings.json", {}) or {}
    old_reports = _read(configs_dir / "yoy_reports/reports.json", {}) or {}

    migrated = {
        "general/catalog": {
            "version": CONFIG_VERSION,
            "columns": {
                "article": old_settings.get("columna_articulo", "Artículo"),
                "family": old_settings.get("columna_familia", "Familias"),
            },
            "default_family": old_settings.get("familia_por_defecto", "Otro"),
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
                "text_columns": old_cleaning.get("columnas_texto_a_limpiar", ["Artículo"]),
                "drop_columns": old_cleaning.get("columnas_a_eliminar", []),
                "numeric_columns": old_cleaning.get("columnas_a_formatear", []),
            },
            "pricing": {
                "columns": _legacy_pricing_columns(old_pricing),
                "aliases": old_pricing.get("mapeo_nombres", {}),
            },
            "output": {
                "raw_data_sheet": old_reports.get("hoja_datos_crudos", "Datos"),
                "base_columns": old_reports.get("orden_columnas_base", ["Artículo", "Familias"]),
                "summaries": old_reports.get("resumenes", []),
            },
        },
        "cross_check/settings": {
            "version": CONFIG_VERSION,
            "filters": {
                "ignored_articles": old_cross.get("articulos_ignorados", []),
                "ignored_terms": old_cross.get("palabras_ignoradas", ["Total general"]),
            },
            "price_lists": {
                "cost": _legacy_price_map(old_cross.get("columnas_costo", {})),
                "sales": _legacy_price_map(old_cross.get("columnas_venta", {})),
            },
        },
        "yoy_reports/settings": {
            "version": CONFIG_VERSION,
            "input": _legacy_yoy_input(old_reports),
            "output": {
                "default_path": old_reports.get("output_path", "analysis_report.xlsx"),
                "metrics": old_reports.get("metricas_salida", ["unidades", "ventas"]),
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
        for rel in LEGACY_FILES:
            path = configs_dir / rel
            if path.exists():
                target = backup_root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(path), str(target))

    return True


def _legacy_pricing_columns(data: dict) -> dict:
    cols = data.get("columnas_esperadas", [])
    return {
        "article": cols[0] if len(cols) > 0 else "Artículo",
        "database": cols[1] if len(cols) > 1 else "Origen - Base de datos",
        "price": cols[2] if len(cols) > 2 else "Precio",
    }


def _legacy_price_map(data: dict) -> dict:
    return {
        "article_column": data.get("articulo", "Artículo"),
        "price_column": data.get("precio", "Precio"),
    }


def _legacy_yoy_input(data: dict) -> dict:
    ds = data.get("data_source", {})
    return {
        "date_column": ds.get("date_column", "Fecha"),
        "quantity_column": ds.get("quantity_column", "Cantidad"),
        "grouping_column": ds.get("grouping_column", "Familias"),
        "item_column": ds.get("item_column", "Articulo"),
        "branch_column": ds.get("branch_column", "Base"),
        "size_column": ds.get("size_column", data.get("columna_talle", "Talle")),
    }


def profile_readiness(configs_dir: Path) -> Dict[str, Tuple[bool, str]]:
    """Return human-readable readiness for the Config Hub / wizard dashboard."""
    initialize_v2_config(configs_dir)
    catalog = _read(config_path(configs_dir, "general/catalog"), {}) or {}
    families = _read(config_path(configs_dir, "general/families"), {}) or {}
    stores = _read(config_path(configs_dir, "general/network"), {}) or {}
    stock = _read(config_path(configs_dir, "stock_processing/settings"), {}) or {}
    cross = _read(config_path(configs_dir, "cross_check/settings"), {}) or {}
    yoy = _read(config_path(configs_dir, "yoy_reports/settings"), {}) or {}

    columns = catalog.get("columns", {})
    family_rules = families.get("rules", {})
    active = stores.get("active", [])
    pricing_cols = stock.get("pricing", {}).get("columns", {})
    cc_lists = cross.get("price_lists", {})
    yoy_input = yoy.get("input", {})

    return {
        "catalog": (bool(columns.get("article") and columns.get("family") and family_rules),
                    f"{len(family_rules)} families"),
        "stores": (bool(active), f"{len(active)} active stores"),
        "stock": (all(pricing_cols.get(k) for k in ("article", "database", "price")),
                  f"{len(stock.get('cleaning', {}).get('drop_columns', []))} drop rules"),
        "cross_check": (all(cc_lists.get(side, {}).get("article_column") and
                            cc_lists.get(side, {}).get("price_column")
                            for side in ("cost", "sales")),
                        f"{len(cross.get('filters', {}).get('ignored_articles', []))} ignored articles"),
        "yoy": (all(yoy_input.get(k) for k in
                    ("date_column", "quantity_column", "grouping_column", "item_column", "branch_column")),
                f"{len(yoy.get('groups', {}))} report groups"),
    }
