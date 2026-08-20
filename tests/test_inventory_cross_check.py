import pytest
from engine.shared.families import build_family_rules, assign_family
from engine.inventory_cross_check.data_processor import calculate_difference

def test_build_family_rules():
    families = {
        "Remeras": ["001", "002"],
        "Buzos": ["0085", "185"]
    }
    rules = build_family_rules(families)
    # Longitud máxima primero
    assert len(rules[0][0]) == 4
    assert rules[0][0] == "0085"
    # Longitud mínima al final (3 caracteres)
    assert len(rules[-1][0]) == 3

def test_assign_family():
    rules = [("0085", "Buzos"), ("001", "Remeras")]
    assert assign_family("0085-123", rules) == "Buzos"
    assert assign_family("00100-XYZ", rules) == "Remeras"
    assert assign_family("99999-ABC", rules) == "Other"
    assert assign_family("REVISAR | 123", rules) == "REVISAR"

def test_calculate_difference():
    # Stock 10, Conteo 5 -> Faltan 5
    assert calculate_difference(10, 5) == -5
    # Stock -2, Conteo 5 -> Sobran 5 (ignora negativo)
    assert calculate_difference(-2, 5) == 5
    # Stock 0, Conteo 10 -> Sobran 10
    assert calculate_difference(0, 10) == 10
