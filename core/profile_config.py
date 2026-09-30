"""Current Inventory Toolkit profile configuration schema and helpers."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Tuple

from core.configuration_errors import ConfigurationFileError

from core.resource_config import load_resource

CONFIG_VERSION = 3

DEFAULTS: Dict[str, dict] = load_resource("profile_defaults.json")
if any(config.get("version") != CONFIG_VERSION for config in DEFAULTS.values()):
    raise ConfigurationFileError(
        Path(__file__).resolve().parent / "resources" / "profile_defaults.json",
        "bundled profile defaults do not match the current schema version",
    )


def config_path(configs_dir: Path, logical_name: str) -> Path:
    return configs_dir / f"{logical_name}.json"


def _read(path: Path, default: Any = None) -> Any:
    """Read JSON while failing closed for an existing but unreadable file.

    A missing file may legitimately fall back to the caller-provided default.
    Once a file exists, however, malformed JSON must never be treated as if
    configuration were absent.
    """
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return deepcopy(default)
    except json.JSONDecodeError as exc:
        raise ConfigurationFileError(
            path,
            f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}",
        ) from exc
    except (OSError, UnicodeError) as exc:
        raise ConfigurationFileError(path, f"could not be read: {exc}") from exc


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


def validate_config_header(path: Path, data: Any) -> None:
    """Validate the current schema independently of optional legacy migration."""
    if not isinstance(data, dict):
        raise ConfigurationFileError(
            path, f"expected a JSON object, got {type(data).__name__}"
        )
    version = data.get("version")
    if type(version) is not int:
        raise ConfigurationFileError(
            path, f"schema version must be an integer; got {version!r}"
        )
    if version > CONFIG_VERSION:
        raise ConfigurationFileError(
            path,
            f"schema version {version} is newer than supported version {CONFIG_VERSION}",
        )
    if version != CONFIG_VERSION:
        raise ConfigurationFileError(
            path,
            f"schema version {version} requires migration to version {CONFIG_VERSION}",
        )


def ensure_profile_config(configs_dir: Path) -> None:
    """Ensure a profile can be consumed through the current schema."""
    # BEGIN LEGACY_COMPATIBILITY
    from core.legacy_profile_migration import prepare_profile_compatibility

    prepare_profile_compatibility(configs_dir)
    # END LEGACY_COMPATIBILITY
    initialize_profile_config(configs_dir)
    for logical_name in DEFAULTS:
        path = config_path(configs_dir, logical_name)
        validate_config_header(path, _read(path))


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
    yoy_output = yoy.get("output", {})
    yoy_groups = yoy.get("groups", {})
    yoy_metrics = yoy_output.get("metrics", [])
    yoy_branches = [
        branch
        for branches in yoy_groups.values()
        for branch in branches
        if str(branch).strip()
    ]
    metric_columns_ready = (
        bool(yoy_metrics)
        and all(metric in {"units", "sales"} for metric in yoy_metrics)
        and ("units" not in yoy_metrics or bool(yoy_input.get("quantity_column")))
        and ("sales" not in yoy_metrics or bool(yoy_input.get("sales_column")))
    )

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
                    "grouping_column",
                    "item_column",
                    "branch_column",
                )
            )
            and metric_columns_ready
            and bool(yoy_branches),
            f"{len(yoy_groups)} report groups / {len(yoy_metrics)} metrics",
        ),
    }
