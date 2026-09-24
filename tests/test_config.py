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


def test_schema_validation_fallback(tmp_path, monkeypatch):
    # A profile directory with no config JSON files remains harmless.
    profile_dir = tmp_path / "profiles" / "test_dummy" / "configs" / "general"
    profile_dir.mkdir(parents=True)

    monkeypatch.chdir(tmp_path)
    cm = ConfigurationManager(profile="test_dummy")
    assert cm._index == {}
