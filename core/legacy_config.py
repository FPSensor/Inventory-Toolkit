"""Compatibility codec for pre-modular Inventory Toolkit configuration.

The Spanish keys in this file are historical serialized contracts. They are
kept verbatim so old profiles and third-party callers can still be decoded.
Current built-in code must use the English, module-oriented configuration API.
"""

from __future__ import annotations

from typing import Any


def build_legacy_view(config: Any, name: str) -> dict | None:
    """Project current configuration back into a pre-v2 compatibility shape."""
    if name == "familias":
        return config.get_family_rules()
    if name == "stores":
        network = config.get_network_config()
        return {
            "locales_activos": network["active"],
            "grupos_regionales": network["regional_groups"],
        }
    if name == "databases":
        return config.get_stock_database_columns()
    if name == "settings":
        catalog = config.get_catalog()
        return {
            "columna_articulo": catalog["columns"]["article"],
            "columna_familia": catalog["columns"]["family"],
            "familia_por_defecto": catalog["default_family"],
        }
    if name == "cleaning":
        cleaning = config.get_stock_cleaning()
        return {
            "columnas_texto_a_limpiar": cleaning["text_columns"],
            "columnas_a_eliminar": cleaning["drop_columns"],
            "columnas_a_formatear": cleaning["numeric_columns"],
        }
    if name == "pricing":
        pricing = config.get_stock_pricing()
        columns = pricing["columns"]
        return {
            "columnas_esperadas": [
                columns["article"],
                columns["database"],
                columns["price"],
            ],
            "mapeo_nombres": pricing["aliases"],
        }
    if name == "cross_check_settings":
        cross_check = config.get_cross_check_config()
        return {
            "articulos_ignorados": cross_check["filters"]["ignored_articles"],
            "palabras_ignoradas": cross_check["filters"]["ignored_terms"],
            "columnas_costo": {
                "articulo": cross_check["price_lists"]["cost"]["article_column"],
                "precio": cross_check["price_lists"]["cost"]["price_column"],
            },
            "columnas_venta": {
                "articulo": cross_check["price_lists"]["sales"]["article_column"],
                "precio": cross_check["price_lists"]["sales"]["price_column"],
            },
        }
    if name == "reports":
        stock_output = config.get_stock_output()
        yoy = config.get_yoy_reports_config()
        source = yoy["input"]
        output = yoy["output"]
        return {
            "orden_columnas_base": stock_output["base_columns"],
            "hoja_datos_crudos": stock_output["raw_data_sheet"],
            "resumenes": [
                {
                    "nombre_hoja": summary["sheet_name"],
                    "locales_a_incluir": summary["entities"],
                    "titulos": summary["titles"],
                }
                for summary in stock_output["summaries"]
            ],
            "output_path": output["default_path"],
            "metricas_salida": output["metrics"],
            "comparacion_anual": output["annual_comparison"],
            "incluir_talles": output["include_sizes"],
            "columna_talle": source["size_column"],
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
