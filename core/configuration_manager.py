"""Central loader for Inventory Toolkit profile configuration.

Configuration v2 is addressed by logical relative path, e.g.
``general/catalog`` or ``yoy_reports/settings``.  This allows each module to own
its own ``settings.json`` without filename collisions.
"""

import json
from pathlib import Path
from typing import Any, Dict, Type

from pydantic import BaseModel

from core.config_schemas import (
    CatalogConfig, CrossCheckConfig, FamiliesConfig, StockProcessingConfig,
    StoresConfig, YoYReportsConfig,
)
from core.logger import log
from core.profile_config import (
    DEFAULTS, config_path, has_legacy_config, has_v2_config,
    initialize_v2_config, migrate_legacy_config,
)


class ConfigurationManager:
    def __init__(self, profile: str = "demo"):
        self.profile = profile
        self.base_dir = Path("profiles") / profile / "configs"
        if has_legacy_config(self.base_dir) and not has_v2_config(self.base_dir):
            migrate_legacy_config(self.base_dir, remove_legacy=False)
        initialize_v2_config(self.base_dir)
        self._index: Dict[str, Any] = {}
        self.reload()

    def reload(self) -> None:
        self._index.clear()
        if not self.base_dir.exists():
            return
        for json_file in self.base_dir.rglob("*.json"):
            logical = json_file.relative_to(self.base_dir).with_suffix("").as_posix()
            try:
                with json_file.open("r", encoding="utf-8") as fh:
                    self._index[logical] = json.load(fh)
            except Exception as exc:
                log.error("Error loading %s: %s", json_file, exc)

    def get_config(self, name: str, default: Any = None) -> Any:
        """Return raw config by logical path.

        A small compatibility map keeps old callers/plugins functional while
        the built-in application uses the v2 module-oriented API.
        """
        if name in self._index:
            return self._index[name]
        compatibility = {
            "settings": self.get_settings,
            "familias": self.get_familias,
            "stores": self.get_stores,
            "databases": self.get_databases,
            "cleaning": self.get_cleaning_rules,
            "pricing": self.get_pricing_rules,
            "cross_check_settings": self.get_cross_check_settings,
            "reports": self.get_reports,
        }
        getter = compatibility.get(name)
        if getter:
            return getter()
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

    # Native v2 accessors -------------------------------------------------
    def get_catalog(self) -> dict:
        return self._validated("general/catalog", CatalogConfig)

    def get_family_config(self) -> dict:
        return self._validated("general/families", FamiliesConfig)

    def get_store_config(self) -> dict:
        return self._validated("general/network", StoresConfig)

    def get_stock_processing_settings(self) -> dict:
        return self._validated("stock_processing/settings", StockProcessingConfig)

    def get_cross_check_config(self) -> dict:
        return self._validated("cross_check/settings", CrossCheckConfig)

    def get_yoy_config(self) -> dict:
        return self._validated("yoy_reports/settings", YoYReportsConfig)

    # Compatibility-shaped accessors ------------------------------------
    # Engines keep their established contracts; only storage is reorganized.
    def get_familias(self) -> Dict[str, list]:
        return self.get_family_config()["rules"]

    def get_stores(self) -> dict:
        cfg = self.get_store_config()
        return {
            "locales_activos": cfg["active"],
            "grupos_regionales": cfg["regional_groups"],
        }

    def get_databases(self) -> dict:
        return self.get_store_config()["stock_database_columns"]

    def get_settings(self) -> dict:
        cfg = self.get_catalog()
        return {
            "columna_articulo": cfg["columns"]["article"],
            "columna_familia": cfg["columns"]["family"],
            "familia_por_defecto": cfg["default_family"],
        }

    def get_cleaning_rules(self) -> dict:
        cleaning = self.get_stock_processing_settings()["cleaning"]
        return {
            "columnas_texto_a_limpiar": cleaning["text_columns"],
            "columnas_a_eliminar": cleaning["drop_columns"],
            "columnas_a_formatear": cleaning["numeric_columns"],
        }

    def get_pricing_rules(self) -> dict:
        pricing = self.get_stock_processing_settings()["pricing"]
        cols = pricing["columns"]
        return {
            "columnas_esperadas": [cols["article"], cols["database"], cols["price"]],
            "mapeo_nombres": pricing["aliases"],
        }

    def get_cross_check_settings(self) -> dict:
        cfg = self.get_cross_check_config()
        return {
            "articulos_ignorados": cfg["filters"]["ignored_articles"],
            "palabras_ignoradas": cfg["filters"]["ignored_terms"],
            "columnas_costo": {
                "articulo": cfg["price_lists"]["cost"]["article_column"],
                "precio": cfg["price_lists"]["cost"]["price_column"],
            },
            "columnas_venta": {
                "articulo": cfg["price_lists"]["sales"]["article_column"],
                "precio": cfg["price_lists"]["sales"]["price_column"],
            },
        }

    def get_reports(self) -> dict:
        stock = self.get_stock_processing_settings()["output"]
        yoy = self.get_yoy_config()
        inp, out = yoy["input"], yoy["output"]
        # Compatibility composite for older callers.  The physical files are
        # separate and correctly owned by their modules.
        return {
            "orden_columnas_base": stock["base_columns"],
            "hoja_datos_crudos": stock["raw_data_sheet"],
            "resumenes": stock["summaries"],
            "output_path": out["default_path"],
            "metricas_salida": out["metrics"],
            "comparacion_anual": out["annual_comparison"],
            "incluir_talles": out["include_sizes"],
            "columna_talle": inp["size_column"],
            "data_source": {
                "date_column": inp["date_column"],
                "quantity_column": inp["quantity_column"],
                "grouping_column": inp["grouping_column"],
                "item_column": inp["item_column"],
                "branch_column": inp["branch_column"],
                "size_column": inp["size_column"],
            },
            "report_structures": yoy["groups"],
        }

    def get_yoy_settings(self) -> dict:
        return self.get_reports()
