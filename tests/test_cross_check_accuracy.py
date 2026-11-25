"""Regressions for inputs that used to produce wrong figures without any error."""

from argparse import Namespace

import pandas as pd
import pytest

from core.runtime import paths as app_paths
from engine.inventory_cross_check.generator import run_cross_check


@pytest.fixture
def cross(tmp_path, monkeypatch):
    monkeypatch.setattr(app_paths, "PROFILES_ROOT", tmp_path / "profiles")

    def run(system, readings, prices=(("AA-1", 100.0),), **options):
        paths = {name: str(tmp_path / f"{name}.xlsx") for name in ("system", "count", "price", "out")}
        pd.DataFrame(system, columns=["Artículo", "Cantidad"]).to_excel(paths["system"], index=False)
        pd.DataFrame(readings).to_excel(paths["count"], index=False, header=False)
        pd.DataFrame(prices, columns=["Artículo", "Precio"]).to_excel(paths["price"], index=False)
        result = run_cross_check(Namespace(
            cross_check_system=paths["system"], cross_check_count=paths["count"],
            shared_cost=paths["price"], shared_sales=paths["price"],
            cross_check_out=paths["out"], cross_check_profile="accuracy",
            cross_check_partial=False, non_interactive=True,
            **options,
        ))
        return pd.read_excel(result)

    return run


def test_repeated_system_articles_do_not_multiply_the_physical_count(cross):
    assert cross([("AA-1", 3), ("AA-1", 4)], ["AA-1"] * 7).empty

    short = cross([("AA-1", 3), ("AA-1", 4)], ["AA-1"] * 5)
    assert short["Conteo Físico"].tolist() == [5]
    assert short["Diferencia"].tolist() == [-2]


@pytest.mark.parametrize("reading", ["abc-1", "ABC-1", "abc-1XL"])
def test_article_case_never_creates_phantom_differences(cross, reading):
    assert cross([("abc-1", 1)], [reading], [("abc-1", 100.0)]).empty


def test_price_lists_match_articles_regardless_of_case(cross):
    result = cross([("AA-1", 5)], ["AA-1"], [("aa-1", 100.0)])
    assert result["CTOTAL"].tolist() == [-400]


def test_multi_column_count_is_rejected_instead_of_reading_the_wrong_column(cross):
    with pytest.raises(ValueError, match="one column"):
        cross([("AA-1", 2)], [["AA-1", 2], ["AA-1", 2]])


def test_empty_count_is_rejected_instead_of_reporting_everything_missing(cross):
    with pytest.raises(ValueError, match="no scanner readings"):
        cross([("AA-1", 2)], [])


def test_cross_check_reads_local_number_formats_and_reports_unclear_ones(cross):
    warnings = []
    result = cross(
        [("AA-1", "1.234,5"), ("AA-2", "abc"), ("AA-3", "1.234")], ["AA-1"], warnings=warnings,
    )
    stock = result.set_index("Artículo")["Stock Sistema"]
    assert stock["AA-1"] == 1234.5
    assert any("2 quantities" in message and "Cantidad" in message for message in warnings)


def test_cross_check_reports_differences_without_price(cross):
    warnings = []
    cross([("AA-1", 2), ("ZZ-9", 1)], ["AA-1"], warnings=warnings)
    assert any("1 products with differences have no cost price" in message for message in warnings)


@pytest.mark.parametrize("raw, value, unclear", [
    ("1.234,5", 1234.5, False),
    ("1,234.5", 1234.5, False),
    ("1.234.567", 1234567, False),
    ("1,5", 1.5, False),
    ("-3", -3, False),
    (2.0, 2, False),
    (1.234, 1.234, False),
    (None, 0, False),
    ("", 0, False),
    ("1.234", 1.234, True),
    ("1,000", 1, True),
    ("abc", 0, True),
])
def test_quantity_parsing(raw, value, unclear):
    from core.files.data_sanitizer import read_quantities

    values, needs_review = read_quantities(pd.Series([raw, "7"], dtype="object"))
    assert values.iloc[0] == value
    assert bool(needs_review.iloc[0]) is unclear


def test_counted_product_known_only_to_price_lists_is_valued(cross):
    # "AA-12" has no system row; it must not become "AA-1" or a review line.
    result = cross([("AA-1", 1)], ["AA-1", "AA-12XL"], [("AA-1", 100.0), ("AA-12", 30.0)])
    assert result[["Artículo", "Diferencia", "CTOTAL"]].values.tolist() == [["AA-12", 1, 30]]


def test_blank_and_conflicting_prices_are_reported(cross):
    warnings = []
    result = cross(
        [("AA-1", 2), ("BB-2", 2)], ["AA-1", "BB-2"],
        [("AA-1", 100.0), ("AA-1", 300.0), ("BB-2", None)], warnings=warnings,
    )
    assert result.set_index("Artículo")["CTOTAL"].to_dict() == {"AA-1": -200, "BB-2": 0}
    text = "\n".join(warnings)
    assert "more than one cost price; their average is used: AA-1" in text
    assert "no cost price" in text and "BB-2" in text


def test_differences_use_the_prices_of_the_counted_store(tmp_path, monkeypatch):
    import json

    monkeypatch.setattr(app_paths, "PROFILES_ROOT", tmp_path / "profiles")
    configs = tmp_path / "profiles" / "stores" / "configs"
    (configs / "general").mkdir(parents=True)
    (configs / "general" / "network.json").write_text(json.dumps({
        "version": 3, "active": ["NORTH", "SOUTH"], "regional_groups": {},
        "stock_database_columns": {"NORTH": "DEPOT-N"},
    }), encoding="utf-8")
    (configs / "cross_check").mkdir()
    prices = {"article_column": "Artículo", "price_column": "Precio", "store_column": "Base"}
    (configs / "cross_check" / "settings.json").write_text(json.dumps({
        "version": 3, "input": {"quantity_column": "Cantidad", "store_column": "Base"},
        "price_lists": {"cost": prices, "sales": prices},
    }), encoding="utf-8")
    paths = {name: str(tmp_path / f"{name}.xlsx") for name in ("system", "count", "price", "out")}
    pd.DataFrame({"Artículo": ["AA-1", "AA-1"], "Base": ["NORTH", "DEPOT-N"], "Cantidad": [2, 1]}).to_excel(
        paths["system"], index=False)
    pd.DataFrame(["AA-1"]).to_excel(paths["count"], index=False, header=False)
    pd.DataFrame({"Artículo": ["AA-1", "AA-1"], "Base": ["NORTH", "SOUTH"], "Precio": [100.0, 900.0]}).to_excel(
        paths["price"], index=False)
    warnings = []
    result = pd.read_excel(run_cross_check(Namespace(
        cross_check_system=paths["system"], cross_check_count=paths["count"],
        shared_cost=paths["price"], shared_sales=paths["price"], cross_check_out=paths["out"],
        cross_check_profile="stores", cross_check_partial=False, warnings=warnings,
    )))
    # The deposit belongs to NORTH, so its prices apply: 2 missing units at 100.
    assert result[["Diferencia", "CTOTAL"]].values.tolist() == [[-2, -200]]
    assert not warnings
