"""Compatibility support for pre-v3 Inventory Toolkit profile storage.

This module deliberately contains historical serialized names. Current code
must not use those names outside this migration boundary. The module is
intended to be removable once all maintained profiles have been migrated.
"""

from __future__ import annotations

import shutil
from copy import deepcopy
from pathlib import Path

from core.business_schema import (
    ARTICLE_COLUMN,
    DATABASE_ORIGIN_COLUMN,
    DEFAULT_FAMILY,
    FAMILY_COLUMN,
    PRICE_COLUMN,
    QUANTITY_COLUMN,
    RAW_DATA_SHEET,
    SIZE_COLUMN,
)
from core.compatibility import warn_legacy_storage, warn_modular_upgrade
from core.configuration_errors import ConfigurationFileError

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


def active_legacy_files(configs_dir: Path) -> list[str]:
    """Return active legacy files, excluding archived migration backups."""
    return [
        relative_path
        for relative_path in LEGACY_FILES
        if (configs_dir / relative_path).exists()
    ]


def has_legacy_config(configs_dir: Path) -> bool:
    return bool(active_legacy_files(configs_dir))


def prepare_profile_compatibility(configs_dir: Path) -> None:
    """Migrate/upgrade old storage before current defaults are initialized."""
    legacy_files = active_legacy_files(configs_dir)
    if legacy_files:
        warn_legacy_storage(configs_dir, legacy_files)
        if not _has_modular_config(configs_dir):
            migrate_legacy_config(configs_dir, remove_legacy=False)

    upgrade_profile_config(configs_dir)


def migrate_legacy_config(configs_dir: Path, *, remove_legacy: bool = False) -> bool:
    """Migrate the old mixed v1 layout into the current module-oriented layout.

    Existing modular files win. Legacy files only populate missing files, so
    rerunning migration is safe. When ``remove_legacy`` is true, source files
    are archived under ``configs/_legacy_v1_backup`` after conversion.
    """
    profile = _profile_api()
    legacy_files = active_legacy_files(configs_dir)
    if not legacy_files:
        profile.initialize_profile_config(configs_dir)
        upgrade_profile_config(configs_dir)
        return False

    warn_legacy_storage(configs_dir, legacy_files)

    old_settings = profile._read(configs_dir / "general/settings.json", {}) or {}
    old_families = profile._read(configs_dir / "general/familias.json", {}) or {}
    old_stores = profile._read(configs_dir / "general/stores.json", {}) or {}
    old_databases = profile._read(configs_dir / "general/databases.json", {}) or {}
    old_cleaning = profile._read(configs_dir / "stock_processing/cleaning.json", {}) or {}
    old_pricing = profile._read(configs_dir / "stock_processing/pricing.json", {}) or {}
    old_cross_check = profile._read(configs_dir / "cross_check/cross_check_settings.json", {}) or {}
    old_reports = profile._read(configs_dir / "yoy_reports/reports.json", {}) or {}

    migrated = {
        "general/catalog": {
            "version": profile.CONFIG_VERSION,
            "columns": {
                "article": old_settings.get("columna_articulo", ARTICLE_COLUMN),
                "family": old_settings.get("columna_familia", FAMILY_COLUMN),
            },
            "default_family": old_settings.get("familia_por_defecto", DEFAULT_FAMILY),
        },
        "general/families": {
            "version": profile.CONFIG_VERSION,
            "rules": old_families or deepcopy(profile.DEFAULTS["general/families"]["rules"]),
        },
        "general/network": {
            "version": profile.CONFIG_VERSION,
            "active": old_stores.get("locales_activos", []),
            "regional_groups": old_stores.get("grupos_regionales", {}),
            "stock_database_columns": old_databases,
        },
        "stock_processing/settings": {
            "version": profile.CONFIG_VERSION,
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
            "version": profile.CONFIG_VERSION,
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
            "version": profile.CONFIG_VERSION,
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
        path = profile.config_path(configs_dir, logical_name)
        if not path.exists():
            profile._write(path, data)

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


def upgrade_profile_config(configs_dir: Path) -> bool:
    """Upgrade modular pre-v3 files in place to the current schema version."""
    profile = _profile_api()
    changed = False
    old_versions: set[int] = set()

    for logical_name, default in profile.DEFAULTS.items():
        path = profile.config_path(configs_dir, logical_name)
        if not path.exists():
            continue

        data = profile._read(path, deepcopy(default))
        if not isinstance(data, dict):
            raise ConfigurationFileError(
                path,
                f"expected a JSON object, got {type(data).__name__}",
            )
        data = data or deepcopy(default)
        original = deepcopy(data)
        version = data.get("version")

        if type(version) is not int:
            raise ConfigurationFileError(
                path,
                f"schema version must be an integer; got {version!r}",
            )
        if version > profile.CONFIG_VERSION:
            raise ConfigurationFileError(
                path,
                f"schema version {version} is newer than supported version {profile.CONFIG_VERSION}",
            )
        if version == profile.CONFIG_VERSION:
            continue

        old_versions.add(version)

        if logical_name == "stock_processing/settings":
            output = data.setdefault("output", {})
            if not isinstance(output, dict):
                raise ConfigurationFileError(path, "'output' must be a JSON object")
            summaries = output.get("summaries", [])
            if not isinstance(summaries, list):
                raise ConfigurationFileError(path, "'output.summaries' must be a JSON array")
            try:
                output["summaries"] = [_upgrade_summary(summary) for summary in summaries]
            except (TypeError, ValueError) as exc:
                raise ConfigurationFileError(
                    path,
                    f"invalid legacy Stock summary structure: {exc}",
                ) from exc
        elif logical_name == "yoy_reports/settings":
            input_config = data.setdefault("input", {})
            if not isinstance(input_config, dict):
                raise ConfigurationFileError(path, "'input' must be a JSON object")
            input_config.setdefault("sales_column", "Monto")
            output = data.setdefault("output", {})
            if not isinstance(output, dict):
                raise ConfigurationFileError(path, "'output' must be a JSON object")
            metrics = output.get("metrics", [])
            if not isinstance(metrics, list):
                raise ConfigurationFileError(path, "'output.metrics' must be a JSON array")
            metric_map = {"unidades": "units", "ventas": "sales"}
            output["metrics"] = [metric_map.get(metric, metric) for metric in metrics]

        data["version"] = profile.CONFIG_VERSION
        if data != original:
            profile._write(path, data)
            changed = True

    if old_versions:
        warn_modular_upgrade(configs_dir, old_versions)
    return changed


def _has_modular_config(configs_dir: Path) -> bool:
    profile = _profile_api()
    return any(profile.config_path(configs_dir, name).exists() for name in profile.DEFAULTS)


def _upgrade_summary(summary: dict) -> dict:
    upgraded = dict(summary)
    legacy_aliases = {
        "nombre_hoja": "sheet_name",
        "locales_a_incluir": "entities",
        "titulos": "titles",
    }
    for legacy_key, current_key in legacy_aliases.items():
        if current_key not in upgraded and legacy_key in upgraded:
            upgraded[current_key] = upgraded[legacy_key]
        upgraded.pop(legacy_key, None)
    return upgraded


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
        "sales_column": source.get("sales_column", "Monto"),
        "grouping_column": source.get("grouping_column", FAMILY_COLUMN),
        "item_column": source.get("item_column", "Articulo"),
        "branch_column": source.get("branch_column", "Base"),
        "size_column": source.get("size_column", data.get("columna_talle", SIZE_COLUMN)),
    }


def _profile_api():
    # Local import avoids a module cycle while keeping historical code physically
    # isolated from the current profile schema implementation.
    from core import profile_config

    return profile_config
