"""Compatibility codec for pre-modular Inventory Toolkit configuration.

The Spanish keys in this file are historical serialized contracts. They are
kept verbatim so old profiles and third-party callers can still be decoded.
Current built-in code must use the English, module-oriented configuration API.
"""

from __future__ import annotations

from typing import Any

from core.resource_config import load_resource

_LEGACY_CONTRACT = load_resource("legacy_contract.json")
LEGACY_KEYS = _LEGACY_CONTRACT["keys"]



def build_legacy_view(config: Any, name: str) -> dict | None:
    """Project current configuration back into a pre-v2 compatibility shape."""
    if name == LEGACY_KEYS["families_api"]:
        return config.get_family_rules()
    if name == "stores":
        network = config.get_network_config()
        return {
            LEGACY_KEYS["active_stores"]: network["active"],
            LEGACY_KEYS["regional_groups"]: network["regional_groups"],
        }
    if name == "databases":
        return config.get_stock_database_columns()
    if name == "settings":
        catalog = config.get_catalog()
        return {
            LEGACY_KEYS["article_column"]: catalog["columns"]["article"],
            LEGACY_KEYS["family_column"]: catalog["columns"]["family"],
            LEGACY_KEYS["default_family"]: catalog["default_family"],
        }
    if name == "cleaning":
        cleaning = config.get_stock_cleaning()
        return {
            LEGACY_KEYS["text_columns"]: cleaning["text_columns"],
            LEGACY_KEYS["drop_columns"]: cleaning["drop_columns"],
            LEGACY_KEYS["numeric_columns"]: cleaning["numeric_columns"],
        }
    if name == "pricing":
        pricing = config.get_stock_pricing()
        columns = pricing["columns"]
        return {
            LEGACY_KEYS["pricing_columns"]: [
                columns["article"],
                columns["database"],
                columns["price"],
            ],
            LEGACY_KEYS["aliases"]: pricing["aliases"],
        }
    if name == "cross_check_settings":
        cross_check = config.get_cross_check_config()
        return {
            LEGACY_KEYS["ignored_articles"]: cross_check["filters"]["ignored_articles"],
            LEGACY_KEYS["ignored_terms"]: cross_check["filters"]["ignored_terms"],
            LEGACY_KEYS["cost_columns"]: {
                LEGACY_KEYS["price_article"]: cross_check["price_lists"]["cost"]["article_column"],
                LEGACY_KEYS["price_value"]: cross_check["price_lists"]["cost"]["price_column"],
            },
            LEGACY_KEYS["sales_columns"]: {
                LEGACY_KEYS["price_article"]: cross_check["price_lists"]["sales"]["article_column"],
                LEGACY_KEYS["price_value"]: cross_check["price_lists"]["sales"]["price_column"],
            },
        }
    if name == "reports":
        stock_output = config.get_stock_output()
        yoy = config.get_yoy_reports_config()
        source = yoy["input"]
        output = yoy["output"]
        return {
            LEGACY_KEYS["base_columns"]: stock_output["base_columns"],
            LEGACY_KEYS["raw_data_sheet"]: stock_output["raw_data_sheet"],
            LEGACY_KEYS["summaries"]: [
                {
                    LEGACY_KEYS["summary_sheet"]: summary["sheet_name"],
                    LEGACY_KEYS["summary_entities"]: summary["entities"],
                    LEGACY_KEYS["summary_titles"]: summary["titles"],
                }
                for summary in stock_output["summaries"]
            ],
            "output_path": output["default_path"],
            LEGACY_KEYS["metrics"]: output["metrics"],
            LEGACY_KEYS["annual_comparison"]: output["annual_comparison"],
            LEGACY_KEYS["include_sizes"]: output["include_sizes"],
            LEGACY_KEYS["size_column"]: source["size_column"],
            "data_source": {
                "date_column": source["date_column"],
                "quantity_column": source["quantity_column"],
                "sales_column": source["sales_column"],
                "grouping_column": source["grouping_column"],
                "item_column": source["item_column"],
                "branch_column": source["branch_column"],
                "size_column": source["size_column"],
            },
            "report_structures": yoy["groups"],
        }
    return None
