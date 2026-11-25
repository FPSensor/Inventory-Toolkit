"""Cross Check and YoY requests behave the same for every interface."""
import pandas as pd
import pytest

from core.runtime import paths
from core.config.json_documents import read_document, write_documents
from core.profiles.profile_creation import create_profile
from core.profiles.profile_store import load_last_paths
from core.workflow_errors import ErrorCode, WorkflowError
from workflows import cross, yoy


@pytest.fixture
def profile(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path / "profiles")
    name = create_profile("Shop", "", ["cross_check", "yoy_reports"])
    document = paths.profile_configs_root(name) / "yoy_reports/settings.json"
    write_documents({document: {**read_document(document), "groups": {"All": ["North"]}}})
    return name


def save(path, **columns):
    pd.DataFrame(columns).to_excel(path, index=False)
    return str(path)


def test_cross_check_from_request_to_report(profile, tmp_path):
    prices = save(tmp_path / "prices.xlsx", SKU=["A"], Cost=[2], Price=[5])
    pd.DataFrame(["A", "A"]).to_excel(tmp_path / "count.xlsx", index=False, header=False)
    request = cross.CrossRequest(
        profile, save(tmp_path / "system.xlsx", SKU=["A"], Quantity=[1]), str(tmp_path / "count.xlsx"),
        prices, prices, output=str(tmp_path / "result"), consolidate=True)
    result = cross.prepare(request, cross.check(request)).run()
    assert result.output.endswith("result.xlsx") and pd.read_excel(result.output)["Diferencia"].tolist() == [1]
    assert set(load_last_paths(profile)["cross_check"]) == {"system", "count", "cost", "sales", "out"}


def sales(tmp_path, profile, **options):
    path = save(tmp_path / "sales.xlsx", Date=pd.to_datetime(["2026-01-02", "2025-01-02"]), SKU=["A", "A"],
                Location=["North"] * 2, Quantity=[3, 2], Category=["Food"] * 2, Revenue=[30, 20])
    values = {"start": "2026-01-01", "end": "2026-01-31", "output": str(tmp_path / "yoy"), **options}
    return yoy.YoYRequest(profile, path, **values)


def test_yoy_from_request_to_report(profile, tmp_path):
    totals = []
    request = sales(tmp_path, profile)
    result = yoy.prepare(request, yoy.check(request)).run(stats=totals.append)
    assert result.output.endswith("yoy.xlsx")
    assert "3 vs 2 (+50.0%)" in totals[0].render()


@pytest.mark.parametrize("start, end", [("", ""), ("2026-13-01", "2026-12-31"), ("01/02/2026", "2026-12-31"), ("2026-02-01", "2026-01-01")])
def test_an_unusable_period_has_its_own_error(profile, tmp_path, start, end):
    with pytest.raises(WorkflowError) as error:
        yoy.check(sales(tmp_path, profile, start=start, end=end))
    assert error.value.code is ErrorCode.PERIOD_INVALID


def test_the_period_includes_the_whole_last_day():
    assert yoy.period("2026-01-01", " 2026-01-31 ")[1] == pd.Timestamp("2026-01-31 23:59:59")


def test_selected_inputs_are_remembered_even_if_the_run_stops(profile, tmp_path):
    request = sales(tmp_path, profile, start="")
    with pytest.raises(WorkflowError):
        yoy.check(request)
    assert load_last_paths(profile)["yoy_reports"] == {"file": request.sales}


def test_checking_a_request_never_edits_the_profile(profile, tmp_path):
    before = yoy.settings(profile)
    config = yoy.check(sales(tmp_path, profile, sales_amounts=True, annual_comparison=True))
    config["input"]["date_column"] = "changed"
    assert yoy.settings(profile) == before


def test_a_period_the_file_does_not_cover_is_not_reported_as_a_fall(profile, tmp_path):
    request = sales(tmp_path, profile, start="2026-03-01", end="2026-03-31")
    with pytest.raises(WorkflowError) as error:
        yoy.prepare(request, yoy.check(request)).run()
    assert error.value.code is ErrorCode.PERIOD_WITHOUT_SALES
    assert not (tmp_path / "yoy.xlsx").exists()


def test_a_missing_previous_year_is_a_warning(profile, tmp_path):
    request = sales(tmp_path, profile, start="2025-01-01", end="2025-01-31")
    result = yoy.prepare(request, yoy.check(request)).run()
    assert len(result.warnings) == 1 and "previous year" in result.warnings[0]


def test_csv_sales_by_unit_price(profile, tmp_path):
    document = paths.profile_configs_root(profile) / "yoy_reports/settings.json"
    settings = read_document(document)
    settings["input"]["sales_values"] = "unit_price"
    write_documents({document: settings})
    path = tmp_path / "sales.csv"
    path.write_text("Date;SKU;Location;Quantity;Category;Revenue\n25/01/2026;007;North;1,5;Food;10\n"
                    "02/01/2025;007;North;2;Food;10\n;;;;;\n", encoding="utf-8")
    totals = []
    request = yoy.YoYRequest(profile, str(path), "2026-01-01", "2026-01-31", sales_amounts=True, output=str(tmp_path / "o"))
    result = yoy.prepare(request, yoy.check(request)).run(stats=totals.append)
    assert "15.00 vs 20.00 (-25.0%)" in totals[0].render()
    assert result.output.endswith("o.xlsx")
