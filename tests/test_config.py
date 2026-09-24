import json

import pytest
from pydantic import ValidationError

from core.config_schemas import CatalogConfig
from core.configuration_manager import ConfigurationManager
from core.profile_config import CONFIG_VERSION, ensure_profile_config


def test_configuration_manager_loading():
    config = ConfigurationManager(profile="demo")

    families = config.get_family_rules()
    assert families["Buzos C Capucha"] == ["0085", "185", "085"]

    network = config.get_network_config()
    assert "VIRREYES" in network["active"]
    assert network["regional_groups"]["NRW"] == ["LIBERT.R", "PASO.R", "P.OESTE"]

    cleaning = config.get_stock_cleaning()
    assert "Artículo" in cleaning["text_columns"]
    assert "CENTRAL" in cleaning["drop_columns"]

    pricing = config.get_stock_pricing()
    assert pricing["columns"]["database"] == "Origen - Base de datos"
    assert pricing["aliases"]["Origen - Base de datos"] == "Base"

    cross_check = config.get_cross_check_config()
    assert "12060-142" in cross_check["filters"]["ignored_articles"]
    assert cross_check["price_lists"]["cost"] == {
        "article_column": "Artículo",
        "price_column": "Precio",
    }

    stock_output = config.get_stock_output()
    assert stock_output["raw_data_sheet"] == "Datos"
    assert stock_output["summaries"][0]["sheet_name"] == "Nrw.I"

    yoy = config.get_yoy_reports_config()
    assert yoy["input"]["date_column"] == "Fecha"
    assert yoy["output"]["metrics"] == ["units", "sales"]

    missing = config.get_config("missing/config", default={"default_key": True})
    assert missing == {"default_key": True}



def test_current_schema_rejects_outdated_version():
    with pytest.raises(ValidationError):
        CatalogConfig.model_validate({
            "version": CONFIG_VERSION - 1,
            "columns": {"article": "SKU", "family": "Family"},
            "default_family": "Other",
        })

def test_empty_profile_bootstraps_current_defaults(tmp_path, monkeypatch):
    profile_dir = tmp_path / "profiles" / "test_dummy" / "configs" / "general"
    profile_dir.mkdir(parents=True)

    monkeypatch.chdir(tmp_path)
    config = ConfigurationManager(profile="test_dummy")
    assert config.get_catalog()["columns"]["article"] == "Artículo"
    assert config.get_family_config()["rules"]["REVISAR"] == ["REVISAR", "revisar"]
    assert config.get_stock_processing_config()["version"] == CONFIG_VERSION
    assert config.get_cross_check_config()["version"] == CONFIG_VERSION
    assert config.get_yoy_reports_config()["version"] == CONFIG_VERSION


# BEGIN LEGACY_COMPATIBILITY
def test_legacy_profile_migrates_without_changing_business_contract(tmp_path, monkeypatch):
    base = tmp_path / "profiles" / "legacy" / "configs"
    legacy_files = {
        "general/settings.json": {
            "columna_articulo": "SKU",
            "columna_familia": "Family",
            "familia_por_defecto": "Other",
        },
        "general/familias.json": {"Shirts": ["01", "001"]},
        "general/stores.json": {
            "locales_activos": ["A"],
            "grupos_regionales": {"ALL": ["A"]},
        },
        "general/databases.json": {"A": "DB_A"},
        "stock_processing/cleaning.json": {
            "columnas_texto_a_limpiar": ["SKU"],
            "columnas_a_eliminar": ["Noise"],
            "columnas_a_formatear": ["A"],
        },
        "stock_processing/pricing.json": {
            "columnas_esperadas": ["SKU", "Origin", "Price"],
            "mapeo_nombres": {"Origin": "Base"},
        },
        "cross_check/cross_check_settings.json": {
            "articulos_ignorados": ["X"],
            "palabras_ignoradas": ["TOTAL"],
            "columnas_costo": {"articulo": "SKU", "precio": "Cost"},
            "columnas_venta": {"articulo": "SKU", "precio": "Retail"},
        },
        "yoy_reports/reports.json": {
            "orden_columnas_base": ["SKU", "Family"],
            "hoja_datos_crudos": "Raw",
            "resumenes": [],
            "output_path": "yoy.xlsx",
            "data_source": {
                "date_column": "Date",
                "quantity_column": "Qty",
                "grouping_column": "Family",
                "item_column": "SKU",
                "branch_column": "Store",
            },
            "report_structures": {"G": ["A"]},
        },
    }
    for relative_path, payload in legacy_files.items():
        path = base / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    config = ConfigurationManager("legacy")

    assert config.get_catalog()["columns"]["article"] == "SKU"
    assert config.get_family_rules() == {"Shirts": ["01", "001"]}
    assert config.get_stock_database_columns() == {"A": "DB_A"}
    assert config.get_stock_cleaning()["drop_columns"] == ["Noise"]
    assert config.get_stock_pricing()["columns"] == {
        "article": "SKU",
        "database": "Origin",
        "price": "Price",
    }
    assert config.get_cross_check_config()["price_lists"]["sales"]["price_column"] == "Retail"
    assert config.get_stock_output()["raw_data_sheet"] == "Raw"
    assert config.get_yoy_reports_config()["input"]["date_column"] == "Date"
    assert (base / "general/catalog.json").exists()
    assert (base / "stock_processing/settings.json").exists()
    assert (base / "yoy_reports/settings.json").exists()


def test_v2_modular_profile_upgrades_internal_keys_to_english(tmp_path):
    configs = tmp_path / "configs"
    stock_path = configs / "stock_processing" / "settings.json"
    yoy_path = configs / "yoy_reports" / "settings.json"
    stock_path.parent.mkdir(parents=True)
    yoy_path.parent.mkdir(parents=True)

    stock_path.write_text(json.dumps({
        "version": 2,
        "output": {
            "summaries": [{
                "nombre_hoja": "Summary",
                "locales_a_incluir": ["A"],
                "titulos": ["Familias"],
            }]
        },
    }), encoding="utf-8")
    yoy_path.write_text(json.dumps({
        "version": 2,
        "output": {"metrics": ["unidades", "ventas"]},
    }), encoding="utf-8")

    ensure_profile_config(configs)
    stock = json.loads(stock_path.read_text(encoding="utf-8"))
    yoy = json.loads(yoy_path.read_text(encoding="utf-8"))

    assert stock["version"] == CONFIG_VERSION
    assert stock["output"]["summaries"] == [{
        "sheet_name": "Summary",
        "entities": ["A"],
        "titles": ["Familias"],
    }]
    assert yoy["version"] == CONFIG_VERSION
    assert yoy["output"]["metrics"] == ["units", "sales"]
# END LEGACY_COMPATIBILITY
