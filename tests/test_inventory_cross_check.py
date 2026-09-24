import pytest
from engine.shared.families import build_family_rules, assign_family
from engine.inventory_cross_check.data_processor import calculate_difference, normalize_article

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
    # System stock -2, physical count 5 -> difference is 5; negative system stock is ignored.
    assert calculate_difference(-2, 5) == 5
    # Stock 0, Conteo 10 -> Sobran 10
    assert calculate_difference(0, 10) == 10


def test_normalize_article_variable_length_longest_prefix():
    # Scanner data may append size/color to variable-length article codes.
    # The master stock is the source of truth; no fixed substring length is valid.
    master_base = [
        "11111",
        "11111-2",
        "11111-261",
        "LONG-ARTICLE-12345",
    ]
    master_set = {article.upper() for article in master_base}

    assert normalize_article("11111-261XXLH1", master_base, master_set) == "11111-261"
    assert normalize_article("LONG-ARTICLE-12345XLRED", master_base, master_set) == "LONG-ARTICLE-12345"


def test_normalize_article_exact_match_and_review_fallback():
    master_base = ["11111-261", "ABC-123"]
    master_set = {article.upper() for article in master_base}

    # Exact matches are normalized to uppercase, matching system-stock normalization.
    assert normalize_article("abc-123", master_base, master_set) == "ABC-123"

    # Unknown readings must never be guessed, truncated, or discarded.
    raw_unknown = "UNKNOWN-XXLH1"
    assert normalize_article(raw_unknown, master_base, master_set) == f"REVISAR | {raw_unknown}"
