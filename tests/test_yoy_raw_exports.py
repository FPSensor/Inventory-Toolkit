"""Sales exports are read as downloaded, without editing them in Excel."""
import pandas as pd
import pytest

from core.runtime import paths as app_paths
from core.config.profile_config import ensure_profile_config
from engine.yoy_reports.data_processor import process_sales_data

START, END = pd.Timestamp("2026-01-01"), pd.Timestamp("2026-01-31")
HEADERS = ["Origen", "Codigo", "Dia", "Unidades", "Importe"]


def config(**values):
    return {"input": {"date_column": "Dia", "item_column": "Codigo", "branch_column": "Origen",
                      "variant_column": "", "grouping_column": "Codigo", "quantity_column": "Unidades",
                      "sales_column": "Importe", **values},
            "output": {"metrics": ["units"], "include_variants": False}}


def export(tmp_path, total=(None, None, "3", "1.200,00", "2.500,50"), rows=None):
    rows = rows or [("LOCAL", "A1", pd.Timestamp("2026-01-02"), 1000, 2000.25),
                    ("DSLOCAL", "A1", pd.Timestamp("2026-01-03"), 201, 600.25),
                    ("OTRO", "A2", pd.Timestamp("2025-01-03"), -1, -100)]
    path = tmp_path / "sales.xlsx"
    pd.DataFrame(rows + ([total] if total else []), columns=HEADERS).to_excel(path, index=False)
    return path


def test_aliases_count_one_location_as_another(tmp_path):
    current, previous, _ = process_sales_data(export(tmp_path), START, END, config(branch_aliases={"DSLOCAL": "LOCAL"}))
    assert current["Origen"].tolist() == ["LOCAL", "LOCAL"]
    assert current["Unidades"].sum() == 1201
    assert previous["Origen"].tolist() == ["OTRO"]


def test_without_aliases_locations_are_unchanged(tmp_path):
    current, _, _ = process_sales_data(export(tmp_path), START, END, config())
    assert current["Origen"].tolist() == ["LOCAL", "DSLOCAL"]


@pytest.mark.parametrize("total, column", [
    ((None, None, "3", "1.201,00", "2.500,50"), "Unidades"),
    ((None, None, "3", "1.200,00", "2.500,40"), "Importe"),
])
def test_a_total_that_does_not_match_stops_the_report(tmp_path, total, column):
    with pytest.raises(ValueError, match=f"totals do not match: '{column}'"):
        process_sales_data(export(tmp_path, total), START, END, config())


@pytest.mark.parametrize("rows, total", [
    ([1000.5, 200.25], "1.200,75"), ([1000.5, 200.25], "1,200.75"), ([1000.5, 200.25], "1200.75"),
    ([0.734, 0.5], "1.234"), ([0.734, 0.5], "1,234"), ([1000, 234], "1.234"), ([1000, 234], "1,234"),
    ([-5, 1], "-4"),
])
def test_totals_are_read_in_any_number_format(tmp_path, rows, total):
    lines = [("LOCAL", "A1", pd.Timestamp("2026-01-02"), value, value) for value in rows]
    current, _, _ = process_sales_data(export(tmp_path, (None, None, "2", total, total), lines), START, END, config())
    assert len(current) == len(rows)
    with pytest.raises(ValueError, match="do not match"):
        process_sales_data(export(tmp_path, (None, None, "2", total, total), lines[:1]), START, END, config())


def test_a_numeric_total_without_date_is_verified(tmp_path):
    lines = [("LOCAL", "A1", pd.Timestamp("2026-01-02"), 2, 5.5)]
    current, _, _ = process_sales_data(export(tmp_path, (None, None, None, 2, 5.5), lines), START, END, config())
    assert len(current) == 1
    with pytest.raises(ValueError, match="do not match"):
        process_sales_data(export(tmp_path, (None, None, None, 3, 5.5), lines), START, END, config())


def test_a_dated_sale_without_item_or_location_is_not_a_total(tmp_path):
    lines = [("LOCAL", "A1", pd.Timestamp("2026-01-02"), 2, 5.5)]
    current, _, _ = process_sales_data(
        export(tmp_path, (None, None, pd.Timestamp("2026-01-03"), 7, 1), lines), START, END, config())
    assert current["Unidades"].sum() == 9


def test_quantities_that_cannot_be_read_are_caught_by_the_total(tmp_path):
    rows = [("LOCAL", "A1", pd.Timestamp("2026-01-02"), "1.200,5", 10)]
    with pytest.raises(ValueError, match="do not match"):
        process_sales_data(export(tmp_path, (None, None, "1", "1.200,50", "10,00"), rows), START, END, config())


@pytest.mark.parametrize("total", [None, (None, "A9", "3", "9,00", "9,00"), (None, None, "x", "Subtotal", "n/d")])
def test_files_without_a_recognizable_total_are_accepted(tmp_path, total):
    current, _, _ = process_sales_data(export(tmp_path, total), START, END, config())
    assert current["Unidades"].sum() == 1201


def test_aliases_are_editable_from_guided_setup(tmp_path, monkeypatch):
    from core.setup.setup_service import SetupSession

    monkeypatch.setattr(app_paths, "PROFILES_ROOT", tmp_path)
    ensure_profile_config(tmp_path / "shop" / "configs")
    session = SetupSession("shop", "yoy_reports", include_advanced=True)
    session.save_step("yoy_source_values", {
        "input.branch_aliases": {"DSLOCAL": "LOCAL"}, "input.code_tokenization": "first_token",
        "input.sales_values": "line_total", "input.all_sheets": False,
    })
    step = next(step for step in session.all_steps if step.id == "yoy_source_values")
    saved = session.data(step)["input"]
    assert (saved["branch_aliases"], saved["code_tokenization"]) == ({"DSLOCAL": "LOCAL"}, "first_token")


@pytest.mark.parametrize("mode, items, variants", [
    ("first_token", ["01008-ORG", "01008-ORG"], ["S", "XXL"]),
    ("whole", ["01008-ORG TABLAS", "01008-ORG"], ["S S", "XXL  XXL"]),
])
def test_codes_can_be_separated_from_their_description(tmp_path, mode, items, variants):
    path = tmp_path / "sales.xlsx"
    pd.DataFrame({"Origen": ["LOCAL"] * 3, "Codigo": ["01008-ORG TABLAS", "01008-ORG", None],
                  "Talle": ["S S", "XXL  XXL", None], "Dia": [pd.Timestamp("2026-01-02")] * 3,
                  "Unidades": [1, 2, 0], "Importe": [1, 2, 0]}).to_excel(path, index=False)
    current, _, _ = process_sales_data(path, START, END, config(variant_column="Talle", code_tokenization=mode))
    assert current["Codigo"].tolist()[:2] == items
    assert current["Talle"].tolist()[:2] == variants
    assert current[["Codigo", "Talle"]].iloc[2].isna().all()
