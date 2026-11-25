"""Sales exports are read as downloaded, without editing them in Excel."""
import pandas as pd
import pytest

from core import paths as app_paths
from core.profile_config import ensure_profile_config
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


def test_quantities_that_cannot_be_read_are_caught_by_the_total(tmp_path):
    rows = [("LOCAL", "A1", pd.Timestamp("2026-01-02"), "1.200,5", 10)]
    with pytest.raises(ValueError, match="do not match"):
        process_sales_data(export(tmp_path, (None, None, "1", "1.200,50", "10,00"), rows), START, END, config())


@pytest.mark.parametrize("total", [None, (None, "A9", "3", "9,00", "9,00"), (None, None, "x", "Subtotal", "n/d")])
def test_files_without_a_recognizable_total_are_accepted(tmp_path, total):
    current, _, _ = process_sales_data(export(tmp_path, total), START, END, config())
    assert current["Unidades"].sum() == 1201


def test_aliases_are_editable_from_guided_setup(tmp_path, monkeypatch):
    from core.setup_service import SetupSession

    monkeypatch.setattr(app_paths, "PROFILES_ROOT", tmp_path)
    ensure_profile_config(tmp_path / "shop" / "configs")
    session = SetupSession("shop", "yoy_reports", include_advanced=True)
    session.save_step("yoy_branch_aliases", {"input.branch_aliases": {"DSLOCAL": "LOCAL"}})
    step = next(step for step in session.all_steps if step.id == "yoy_branch_aliases")
    assert session.data(step)["input"]["branch_aliases"] == {"DSLOCAL": "LOCAL"}
