import pytest
from core.configuration_manager import ConfigurationManager, ConfigNode

def test_config_node_encapsulation():
    data = {"clave": "valor", "anidado": {"subclave": 1}}
    nodo = ConfigNode(data)
    assert nodo.clave == "valor"
    assert nodo.anidado.subclave == 1

def test_configuration_manager_dual_contract():
    cm = ConfigurationManager(profile="demo")
    
    settings_raw = cm.get_config("settings")
    assert isinstance(settings_raw, dict)
    
    if hasattr(cm, "settings"):
        assert isinstance(cm.settings, ConfigNode)
