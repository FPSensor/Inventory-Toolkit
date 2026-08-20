import pytest
from pathlib import Path
from core.configuration_manager import ConfigurationManager

def test_configuration_manager_loading():
    cm = ConfigurationManager(profile="demo")
    
    # Validar getters principales
    assert isinstance(cm.get_familias(), dict)
    assert isinstance(cm.get_stores(), dict)
    assert isinstance(cm.get_cleaning_rules(), dict)
    assert isinstance(cm.get_reports(), dict)
    
    # Validar get_config genérico y defaults
    settings = cm.get_config("settings")
    assert isinstance(settings, dict)
    assert "columna_articulo" in settings
    
    non_existent = cm.get_config("non_existent_config_file", default={"default_key": True})
    assert non_existent == {"default_key": True}

def test_schema_validation_fallback(tmp_path, monkeypatch):
    # Validar que un perfil sin schema.json explícito no rompe la carga
    profile_dir = tmp_path / "profiles" / "test_dummy" / "configs" / "general"
    profile_dir.mkdir(parents=True)
    
    monkeypatch.chdir(tmp_path)
    cm = ConfigurationManager(profile="test_dummy")
    assert cm._index == {}
