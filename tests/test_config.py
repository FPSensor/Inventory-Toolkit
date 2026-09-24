from core.configuration_manager import ConfigurationManager


def test_configuration_manager_loading():
    cm = ConfigurationManager(profile="demo")

    # Typed accessors must preserve the real shape/content of each JSON file.
    familias = cm.get_familias()
    assert familias["Buzos C Capucha"] == ["0085", "185", "085"]

    stores = cm.get_stores()
    assert "VIRREYES" in stores["locales_activos"]
    assert stores["grupos_regionales"]["NRW"] == ["LIBERT.R", "PASO.R", "P.OESTE"]

    cleaning = cm.get_cleaning_rules()
    assert "Artículo" in cleaning["columnas_texto_a_limpiar"]
    assert "CENTRAL" in cleaning["columnas_a_eliminar"]

    pricing = cm.get_pricing_rules()
    assert "Origen - Base de datos" in pricing["columnas_esperadas"]
    assert pricing["mapeo_nombres"]["Origen - Base de datos"] == "Base"

    cross_check = cm.get_cross_check_settings()
    assert "12060-142" in cross_check["articulos_ignorados"]
    assert cross_check["columnas_costo"] == {"articulo": "Artículo", "precio": "Precio"}

    reports = cm.get_reports()
    assert reports["hoja_datos_crudos"] == "Datos"
    assert reports["resumenes"][0]["nombre_hoja"] == "Nrw.I"
    assert reports["data_source"]["date_column"] == "Fecha"
    assert cm.get_yoy_settings() == reports

    # Generic raw access and explicit defaults remain available.
    settings = cm.get_config("settings")
    assert isinstance(settings, dict)
    assert "columna_articulo" in settings

    non_existent = cm.get_config(
        "non_existent_config_file", default={"default_key": True}
    )
    assert non_existent == {"default_key": True}


def test_empty_profile_bootstraps_safe_v2_defaults(tmp_path, monkeypatch):
    profile_dir = tmp_path / "profiles" / "test_dummy" / "configs" / "general"
    profile_dir.mkdir(parents=True)

    monkeypatch.chdir(tmp_path)
    cm = ConfigurationManager(profile="test_dummy")
    assert cm.get_catalog()["columns"]["article"] == "Artículo"
    assert cm.get_family_config()["rules"]["REVISAR"] == ["REVISAR", "revisar"]
    assert "stock_processing/settings" in cm._index
    assert "cross_check/settings" in cm._index
    assert "yoy_reports/settings" in cm._index


def test_legacy_profile_migrates_without_changing_engine_contract(tmp_path, monkeypatch):
    import json
    from pathlib import Path

    base = tmp_path / "profiles" / "legacy" / "configs"
    files = {
        "general/settings.json": {"columna_articulo": "SKU", "columna_familia": "Family", "familia_por_defecto": "Other"},
        "general/familias.json": {"Shirts": ["01", "001"]},
        "general/stores.json": {"locales_activos": ["A"], "grupos_regionales": {"ALL": ["A"]}},
        "general/databases.json": {"A": "DB_A"},
        "stock_processing/cleaning.json": {"columnas_texto_a_limpiar": ["SKU"], "columnas_a_eliminar": ["Noise"], "columnas_a_formatear": ["A"]},
        "stock_processing/pricing.json": {"columnas_esperadas": ["SKU", "Origin", "Price"], "mapeo_nombres": {"Origin": "Base"}},
        "cross_check/cross_check_settings.json": {"articulos_ignorados": ["X"], "palabras_ignoradas": ["TOTAL"], "columnas_costo": {"articulo": "SKU", "precio": "Cost"}, "columnas_venta": {"articulo": "SKU", "precio": "Retail"}},
        "yoy_reports/reports.json": {"orden_columnas_base": ["SKU", "Family"], "hoja_datos_crudos": "Raw", "resumenes": [], "output_path": "yoy.xlsx", "data_source": {"date_column": "Date", "quantity_column": "Qty", "grouping_column": "Family", "item_column": "SKU", "branch_column": "Store"}, "report_structures": {"G": ["A"]}},
    }
    for rel, payload in files.items():
        path = base / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    cm = ConfigurationManager("legacy")
    assert cm.get_settings()["columna_articulo"] == "SKU"
    assert cm.get_familias() == {"Shirts": ["01", "001"]}
    assert cm.get_databases() == {"A": "DB_A"}
    assert cm.get_cleaning_rules()["columnas_a_eliminar"] == ["Noise"]
    assert cm.get_pricing_rules()["columnas_esperadas"] == ["SKU", "Origin", "Price"]
    assert cm.get_cross_check_settings()["columnas_venta"]["precio"] == "Retail"
    reports = cm.get_reports()
    assert reports["hoja_datos_crudos"] == "Raw"
    assert reports["data_source"]["date_column"] == "Date"
    assert (base / "general/catalog.json").exists()
    assert (base / "stock_processing/settings.json").exists()
    assert (base / "yoy_reports/settings.json").exists()
