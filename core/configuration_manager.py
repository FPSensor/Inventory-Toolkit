"""Central loader for Inventory Toolkit profile configuration.

Configuration is addressed by logical relative path, for example
``general/catalog`` or ``yoy_reports/settings``. Each module can therefore own
its own ``settings.json`` without filename collisions.
"""

import json
from core.json_documents import read_document
from typing import Any, Dict, Type

from pydantic import BaseModel

from core.config_schemas import (
    CatalogConfig,
    CrossCheckConfig,
    FamiliesConfig,
    NetworkConfig,
    StockProcessingConfig,
    YoYReportsConfig,
)
from core.configuration_errors import ConfigurationError, ConfigurationFileError
from core.logger import log_debug_event
from core.paths import profile_configs_root
from core.profile_config import DEFAULTS, ensure_profile_config, validate_config_header
from core.module_preferences import enabled_modules, require_enabled


_CONFIG_MODELS: Dict[str, Type[BaseModel]] = {
    "general/catalog": CatalogConfig,
    "general/families": FamiliesConfig,
    "general/network": NetworkConfig,
    "stock_processing/settings": StockProcessingConfig,
    "cross_check/settings": CrossCheckConfig,
    "yoy_reports/settings": YoYReportsConfig,
}


class ConfigurationManager:
    def __init__(self, profile: str = "demo", *, module: str | None = None):
        self.profile = profile
        if module is not None:
            require_enabled(profile, module)
        self.modules = (module,) if module else enabled_modules(profile)
        self.logical_names = {"general/catalog", "general/families", "general/network"} | {
            f"{name}/settings" for name in self.modules}
        self.base_dir = profile_configs_root(profile)
        log_debug_event(
            "config_manager_init",
            profile=profile,
            base_dir=str(self.base_dir),
        )
        try:
            ensure_profile_config(self.base_dir, logical_names=self.logical_names)
            self._index: Dict[str, Any] = {}
            self.reload()
            self.validate_all()
        except ConfigurationError as exc:
            raise ConfigurationError(
                f"Profile '{self.profile}' configuration is not safe to use: {exc}"
            ) from exc

    def reload(self) -> None:
        """Reload all active JSON files without substituting defaults on read errors."""
        self._index.clear()
        if not self.base_dir.exists():
            log_debug_event(
                "config_reload_skipped",
                profile=self.profile,
                reason="base_dir_missing",
                base_dir=str(self.base_dir),
            )
            return

        loaded_files = []
        for json_file in self.base_dir.rglob("*.json"):
            relative = json_file.relative_to(self.base_dir)
            if relative.parts and relative.parts[0] == "_legacy_v1_backup":
                continue
            logical_name = relative.with_suffix("").as_posix()
            if logical_name not in self.logical_names:
                continue
            try:
                self._index[logical_name] = read_document(json_file)
                loaded_files.append(logical_name)
            except json.JSONDecodeError as exc:
                raise ConfigurationFileError(
                    json_file,
                    f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}",
                ) from exc
            except (OSError, UnicodeError) as exc:
                raise ConfigurationFileError(
                    json_file,
                    f"could not be read: {exc}",
                ) from exc

        log_debug_event(
            "config_reload_complete",
            profile=self.profile,
            config_count=len(self._index),
            configs=sorted(loaded_files),
        )

    def validate_all(self) -> None:
        """Validate the complete current profile before any workflow can use it."""
        for logical_name, model in _CONFIG_MODELS.items():
            if logical_name not in self.logical_names:
                continue
            self._validated(logical_name, model)
        log_debug_event(
            "config_profile_validation_ok",
            profile=self.profile,
            config_count=len(_CONFIG_MODELS),
        )

    def get_config(self, logical_name: str, default: Any = None) -> Any:
        """Return raw config by logical path.

        Logical names identify current schema-v3 documents. Built-in modules
        use the typed workflow accessors when possible.
        """
        if logical_name in self._index:
            log_debug_event(
                "config_raw_access",
                profile=self.profile,
                logical_name=logical_name,
                source="current_schema",
            )
            return self._index[logical_name]

        return default if default is not None else {}

    def _validated(self, logical_name: str, model: Type[BaseModel]) -> dict:
        source = "profile" if logical_name in self._index else "default"
        raw = self._index.get(logical_name, DEFAULTS[logical_name])
        path = self.base_dir / f"{logical_name}.json"
        log_debug_event(
            "config_validate",
            profile=self.profile,
            logical_name=logical_name,
            model=model.__name__,
            source=source,
        )
        try:
            validate_config_header(path, raw)
            validated = model.model_validate(raw).model_dump()
            log_debug_event(
                "config_validate_ok",
                profile=self.profile,
                logical_name=logical_name,
                top_level_keys=sorted(validated.keys()),
            )
            return validated
        except Exception as exc:
            raise ConfigurationError(
                f"Invalid configuration '{logical_name}.json' for profile "
                f"'{self.profile}' at '{path}': {exc}"
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
