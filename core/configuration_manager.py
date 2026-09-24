"""Central loader for Inventory Toolkit profile configuration.

Configuration is addressed by logical relative path, for example
``general/catalog`` or ``yoy_reports/settings``. Each module can therefore own
its own ``settings.json`` without filename collisions.
"""

import json
from pathlib import Path
from typing import Any, Dict, Type

from pydantic import BaseModel

from core.config_schemas import (
    CatalogConfig,
    CrossCheckConfig,
    FamiliesConfig,
    StockProcessingConfig,
    NetworkConfig,
    YoYReportsConfig,
)
# BEGIN LEGACY_COMPATIBILITY
from core.compatibility import warn_legacy_api
from core.legacy_config import build_legacy_view
# END LEGACY_COMPATIBILITY
from core.logger import log
from core.profile_config import DEFAULTS, ensure_profile_config


class ConfigurationManager:
    def __init__(self, profile: str = "demo"):
        self.profile = profile
        self.base_dir = Path("profiles") / profile / "configs"
        ensure_profile_config(self.base_dir)
        self._index: Dict[str, Any] = {}
        self.reload()

    def reload(self) -> None:
        self._index.clear()
        if not self.base_dir.exists():
            return
        for json_file in self.base_dir.rglob("*.json"):
            logical_name = json_file.relative_to(self.base_dir).with_suffix("").as_posix()
            try:
                with json_file.open("r", encoding="utf-8") as handle:
                    self._index[logical_name] = json.load(handle)
            except Exception as exc:
                log.error("Error loading %s: %s", json_file, exc)

    def get_config(self, logical_name: str, default: Any = None) -> Any:
        """Return raw config by logical path.

        Pre-v2 short names remain available as a narrow compatibility bridge
        for third-party callers. Built-in modules use the current English API.
        """
        if logical_name in self._index:
            return self._index[logical_name]

        # BEGIN LEGACY_COMPATIBILITY
        legacy_view = build_legacy_view(self, logical_name)
        if legacy_view is not None:
            warn_legacy_api(self.profile, logical_name)
            return legacy_view
        # END LEGACY_COMPATIBILITY
        return default if default is not None else {}

    def _validated(self, logical_name: str, model: Type[BaseModel]) -> dict:
        raw = self._index.get(logical_name, DEFAULTS[logical_name])
        try:
            return model.model_validate(raw).model_dump()
        except Exception as exc:
            raise ValueError(
                f"Invalid configuration '{logical_name}.json' for profile "
                f"'{self.profile}': {exc}"
            ) from exc

    # Native configuration accessors -------------------------------------
    def get_catalog(self) -> dict:
        return self._validated("general/catalog", CatalogConfig)

    def get_family_config(self) -> dict:
        return self._validated("general/families", FamiliesConfig)

    def get_network_config(self) -> dict:
        return self._validated("general/network", NetworkConfig)

    def get_stock_processing_config(self) -> dict:
        return self._validated("stock_processing/settings", StockProcessingConfig)

    def get_cross_check_config(self) -> dict:
        return self._validated("cross_check/settings", CrossCheckConfig)

    def get_yoy_reports_config(self) -> dict:
        return self._validated("yoy_reports/settings", YoYReportsConfig)

    # Convenience accessors used by built-in modules ---------------------
    def get_family_rules(self) -> Dict[str, list]:
        return self.get_family_config()["rules"]

    def get_catalog_columns(self) -> dict:
        return self.get_catalog()["columns"]

    def get_default_family(self) -> str:
        return self.get_catalog()["default_family"]

    def get_active_stores(self) -> list[str]:
        return self.get_network_config()["active"]

    def get_regional_groups(self) -> Dict[str, list]:
        return self.get_network_config()["regional_groups"]

    def get_stock_database_columns(self) -> Dict[str, str]:
        return self.get_network_config()["stock_database_columns"]

    def get_stock_cleaning(self) -> dict:
        return self.get_stock_processing_config()["cleaning"]

    def get_stock_pricing(self) -> dict:
        return self.get_stock_processing_config()["pricing"]

    def get_stock_output(self) -> dict:
        return self.get_stock_processing_config()["output"]
