import json
import re
from argparse import Namespace

import pandas as pd
import pytest
from openpyxl import load_workbook

from core import paths as app_paths
from core.workbook_package import WorkbookPackage, WorkbookPackageError
from engine.stock_processing.excel_renderer import build_summary, render_stock_excel
from engine.stock_processing.pivot_formulas import PivotFormulaError, evaluate
from engine.stock_processing.template_renderer import ReportTemplateError, fill_template
from tests.report_template import HEADERS, build_template

FRAME = pd.DataFrame(
    [
        ("B1", "Remeras", 3, 10.0, 40.0),
        ("B2", "Nuevo", 4, 0.0, 0.0),
        ("B3", "Oculto", 9, 90.0, 90.0),
        ("B4", "Remeras", -1, -5.0, -20.5),
        ("B&<5", "Bermudas", 2, 4.0, 16.0),
    ],
    columns=HEADERS,
)
SUMMARY = {"sheet_name": "Fijo", "entities": ["Local"], "titles": []}


def fill(template, frame=FRAME, **options):
    summary = build_summary(frame, SUMMARY, "Rubro", cost_factor=2, hidden_families=["Oculto"],
                            totals_label="Total", blank_undefined_margin=True)[0]
    return fill_template(template, frame, {"Fijo": summary}, "Base", family_column="Rubro",
                         hidden_families=["Oculto"], totals_label="Total", **options)


@pytest.fixture
def template(tmp_path):
    return build_template(tmp_path / "template.xlsx")


def test_template_rebuilds_every_pivot_from_new_data(template, tmp_path):
    payload, warnings = fill(template)
    output = tmp_path / "out.xlsx"
    output.write_bytes(payload)
    workbook = load_workbook(output)
    rows = lambda name: [list(row) for row in workbook[name].iter_rows(min_row=4, values_only=True)]

    assert warnings == []
    assert rows("Resumen A") == [
        ["Bermudas", 2, 0.5], ["Nuevo", 4, "#DIV/0!"], ["Remeras", 2, pytest.approx(1 - 10 / 19.5)],
        ["Total general", 8, pytest.approx(1 - 18 / 35.5)],
    ]
    # Profile-hidden families apply to every pivot; descending order is kept.
    assert rows("Resumen B") == [["Remeras", 19.5], ["Nuevo", 0], ["Bermudas", 16], ["Total general", 35.5]]
    assert workbook["Resumen A"]["A1"].value == "Informe"
    assert [cell.value for cell in workbook["Fijo"][5]] == ["Total", 8, 9, 35.5, pytest.approx(1 - 18 / 35.5)]
    assert workbook["Base"].max_row == len(FRAME) + 1
    assert workbook["Base"]["A6"].value == "B&<5"
    assert workbook["Base"].auto_filter.ref == "A1:E6"
    pivot = workbook["Resumen A"]._pivots[0]
    assert pivot.location.ref == "A3:C7"
    assert pivot.cache.cacheSource.worksheetSource.ref == "A1:E6"
    assert [item.v for item in pivot.cache.cacheFields[1].sharedItems._fields] == ["Remeras", "Nuevo", "Oculto", "Bermudas"]
    assert "Viejo" not in "".join(
        part.decode("utf-8") for name, part in WorkbookPackage.read(output).parts.items() if "pivot" in name
    )


def test_profile_visibility_replaces_the_template_visibility(template, tmp_path):
    # The fixture hides "Oculto" in pivot A only; both pivots must agree.
    output = tmp_path / "out.xlsx"
    output.write_bytes(fill_template(template, FRAME, {}, "Base", family_column="Rubro")[0])
    workbook = load_workbook(output)
    for name in ("Resumen A", "Resumen B"):
        labels = {row[0] for row in workbook[name].iter_rows(min_row=4, values_only=True)}
        assert "Oculto" in labels
    assert workbook["Resumen A"].cell(8, 2).value == 17


def test_template_visibility_is_kept_for_rows_that_are_not_families(template, tmp_path):
    output = tmp_path / "out.xlsx"
    output.write_bytes(fill_template(template, FRAME, {}, "Base", family_column="SKU")[0])
    labels = [row[0] for row in load_workbook(output)["Resumen A"].iter_rows(min_row=4, values_only=True)]
    assert "Oculto" not in labels


def test_shorter_and_longer_reports_do_not_keep_previous_rows(template, tmp_path):
    for size in (1, 60):
        frame = pd.DataFrame([(f"C{i}", f"Familia {i:02d}", 1, 1.0, 4.0) for i in range(size)], columns=HEADERS)
        output = tmp_path / f"{size}.xlsx"
        output.write_bytes(fill(template, frame)[0])
        sheet = load_workbook(output)["Resumen A"]
        assert sheet.max_row == 3 + size + 1
        assert sheet.cell(sheet.max_row, 2).value == size


def test_verifier_rejects_a_cell_placed_in_another_row(template):
    package = WorkbookPackage.read(template)
    part = package.sheets()["Base"]
    package.parts[part] = re.sub(rb'r="E3"', b'r="E99"', package.parts[part])
    with pytest.raises(WorkbookPackageError, match="E99 is misplaced in row 3"):
        package.validate()


@pytest.mark.parametrize("part, old, new, problem", [
    ("pivotCacheRecords1", b'<x v="2"/>', b'<x v="9"/>', "unknown item"),
    ("pivotCacheRecords1", b'count="3"', b'count="4"', "count mismatch"),
    ("pivotCacheDefinition1", b'ref="A1:E4"', b'ref="A1:E9"', "source range"),
    ("pivotTable1", b'ref="A3:C6"', b'ref="A3:C9"', "location"),
    ("pivotTable1", b'x="2"/>', b'x="7"/>', "outside the cache"),
])
def test_verifier_rejects_inconsistent_pivots(template, part, old, new, problem):
    package = WorkbookPackage.read(template)
    name = next(item for item in package.parts if part in item and not item.endswith(".rels"))
    assert old in package.parts[name]
    package.parts[name] = package.parts[name].replace(old, new, 1)
    with pytest.raises(WorkbookPackageError, match=problem):
        package.validate()


@pytest.mark.parametrize("extra, message", [
    ('<pageFields count="1"><pageField fld="0"/></pageFields>', "report filters"),
    ('<filters count="1"><filter fld="1" type="sum" evalOrder="-1" id="1"/></filters>', "value filters"),
])
def test_unsupported_pivot_layouts_are_rejected(tmp_path, extra, message):
    with pytest.raises(ReportTemplateError, match=message):
        fill(build_template(tmp_path / "t.xlsx", extra=extra))


@pytest.mark.parametrize("change, message", [
    (lambda frame: frame.drop(columns="Local.Costo"), "not produced by this profile"),
    (lambda frame: frame.iloc[0:0], "no stock rows"),
    (lambda frame: frame.assign(Rubro=["X", "x", "Y", "Y", "Y"]), "letter case"),
    (lambda frame: frame.assign(Rubro="Oculto"), "hides every item"),
])
def test_unusable_data_is_rejected(template, change, message):
    with pytest.raises(ReportTemplateError, match=message):
        fill(template, change(FRAME))


def test_template_content_is_never_silently_discarded(tmp_path, template):
    workbook = load_workbook(template)
    workbook["Resumen A"]["F4"] = "nota"
    edited = tmp_path / "edited.xlsx"
    workbook.save(edited)
    with pytest.raises(ReportTemplateError, match="F4"):
        fill(edited)


def test_unmanaged_numbers_are_reported(template):
    _payload, warnings = fill_template(template, FRAME, {}, "Base", family_column="Rubro")
    assert len(warnings) == 1 and "'Fijo'" in warnings[0]


@pytest.mark.parametrize("formula, expected", [
    ("1-(A.B*1.5)/'C D'", 0.25), ("-A.B+2*3", 4), ("A.B/0", None), ("=A.B", 2),
])
def test_calculated_fields(formula, expected):
    assert evaluate(formula, ["A", "A.B", "C D"], {"A": 9, "A.B": 2, "C D": 4}.get) == expected


@pytest.mark.parametrize("formula", ["IF(A>1,1,0)", "A^2", "A+", "(A", "Nada"])
def test_unsupported_calculated_fields_are_rejected(formula):
    with pytest.raises(PivotFormulaError):
        evaluate(formula, ["A"], {"A": 1}.get)


def test_standard_report_honors_cost_factor_totals_and_hidden_families(tmp_path):
    path = tmp_path / "standard.xlsx"
    render_stock_excel(str(path), FRAME, [SUMMARY], list(FRAME.columns), "Base", family_column="Rubro",
                       interactive=False, cost_factor=2, hidden_families=("Oculto",), totals_label="Total")
    rows = list(load_workbook(path)["Fijo"].iter_rows(min_row=2, values_only=True))
    assert [row[0] for row in rows] == ["Bermudas", "Nuevo", "Remeras", "Total"]
    assert rows[0][4] == 0.5
    assert rows[-1][1:4] == (8, 9, 35.5)


def _profile(tmp_path, template):
    root = tmp_path / "profiles" / "report"
    for name, value in {
        "general/catalog": {"columns": {"article": "SKU", "family": "Rubro"}, "default_family": "Otro"},
        "general/families": {"rules": {"Remeras": ["R"], "Bermudas": ["B"]}},
        "general/network": {"active": ["Local"], "regional_groups": {}, "stock_database_columns": {}},
        "stock_processing/settings": {
            "cleaning": {"numeric_columns": ["Local"]},
            "pricing": {"columns": {"article": "SKU", "database": "Base", "price": "Precio"}},
            "output": {"raw_data_sheet": "Base", "base_columns": ["SKU", "Rubro"], "template": template,
                       "cost_factor": 2, "totals_label": "Total",
                       "summaries": [{"sheet_name": "Fijo", "entities": ["Local"], "titles": []}]},
        },
    }.items():
        path = root / "configs" / f"{name}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"version": 3, **value}), encoding="utf-8")
    return root


def _run(tmp_path, warnings=None, **options):
    stock, price, output = tmp_path / "s.xlsx", tmp_path / "p.xlsx", tmp_path / "o.xlsx"
    pd.DataFrame({"SKU": ["R1", "B1"], "Local": [2, 3]}).to_excel(stock, index=False)
    prices = pd.DataFrame({"SKU": ["R1", "B1"], "Base": ["Local"] * 2, "Precio": [10.0, 20.0]})
    (prices.iloc[:1] if options else prices).to_excel(price, index=False)
    return run_stock(stock, price, output, warnings, **options), output


def run_stock(stock, price, output, warnings=None, **options):
    from engine.stock_processing.generator import run_stock_processing

    return run_stock_processing(Namespace(
        stock_processing_raw=str(stock), shared_cost=str(price), shared_sales=str(price),
        stock_processing_out=str(output), stock_processing_profile="report", non_interactive=True,
        warnings=[] if warnings is None else warnings, **options,
    ))


def test_stock_processing_uses_the_profile_template(tmp_path, monkeypatch):
    monkeypatch.setattr(app_paths, "PROFILES_ROOT", tmp_path / "profiles")
    root = _profile(tmp_path, "templates/report.xlsx")
    (root / "templates").mkdir()
    build_template(root / "templates" / "report.xlsx")
    result, output = _run(tmp_path)
    assert result == str(output)
    sheet = load_workbook(output)["Resumen A"]
    assert [[cell.value for cell in row] for row in sheet["A4:C6"]] == [
        ["Bermudas", 3, -1], ["Remeras", 2, -1], ["Total general", 5, -1],
    ]


@pytest.mark.parametrize("hidden, expected", [
    (["Remeras"], ["Hidden families have stock that is not included in the report totals (Remeras: 2 units)."]),
    (["Sin Stock"], []), ([], []),
])
def test_hidden_families_with_stock_are_reported(tmp_path, monkeypatch, hidden, expected):
    monkeypatch.setattr(app_paths, "PROFILES_ROOT", tmp_path / "profiles")
    root = _profile(tmp_path, "")
    path = root / "configs" / "stock_processing" / "settings.json"
    settings = json.loads(path.read_text(encoding="utf-8"))
    settings["output"]["hidden_families"] = hidden
    path.write_text(json.dumps(settings), encoding="utf-8")
    warnings = []
    _run(tmp_path, warnings)
    assert warnings == expected


def test_template_settings_are_editable_from_guided_setup(tmp_path, monkeypatch):
    from core.setup_service import SetupSession

    monkeypatch.setattr(app_paths, "PROFILES_ROOT", tmp_path / "profiles")
    root = _profile(tmp_path, "")
    session = SetupSession("report", "stock_processing", include_advanced=True)
    session.save_step("stock_template", {
        "output.template": "templates/r.xlsx", "output.cost_factor": 1.245,
        "output.hidden_families": ["Bolsas"], "output.totals_label": "",
    })
    saved = json.loads((root / "configs" / "stock_processing" / "settings.json").read_text(encoding="utf-8"))["output"]
    assert (saved["template"], saved["cost_factor"], saved["hidden_families"]) == ("templates/r.xlsx", 1.245, ["Bolsas"])
    assert saved["summaries"][0]["sheet_name"] == "Fijo"


def _unit_columns(values):
    return [value for value in values if str(value).startswith("PrecioUnit.")]


@pytest.mark.parametrize("template", ["", "report.xlsx"])
def test_unit_prices_are_opt_in_and_do_not_change_totals(tmp_path, monkeypatch, template):
    monkeypatch.setattr(app_paths, "PROFILES_ROOT", tmp_path / "profiles")
    root = _profile(tmp_path, template)
    if template:
        build_template(root / template)
    _run(tmp_path, include_unit_prices=False)
    totals = pd.read_excel(tmp_path / "o.xlsx", sheet_name="Base")
    _run(tmp_path, include_unit_prices=True)
    detailed = pd.read_excel(tmp_path / "o.xlsx", sheet_name="Base")

    expected = ["PrecioUnit.Costo.Local", "PrecioUnit.Venta.Local"]
    assert _unit_columns(totals) == []
    assert _unit_columns(detailed) == expected
    assert detailed[expected].values.tolist() == [[10, 10], [-1, -1]]
    pd.testing.assert_frame_equal(detailed[totals.columns], totals)
    if template:
        workbook = load_workbook(tmp_path / "o.xlsx")
        assert list(detailed.columns[-2:]) == expected
        assert workbook["Resumen A"]._pivots[0].cache.cacheSource.worksheetSource.ref == "A1:E3"
        assert workbook["Base"].auto_filter.ref == "A1:G3"
    else:
        assert list(detailed.columns) == ["SKU", "Rubro", "Local", *expected, "Local.Costo", "Local.Venta"]


@pytest.mark.parametrize("answers, expected", [([""], False), (["n"], False), (["Y"], True), (["salame", "y"], True)])
def test_console_asks_for_unit_prices_and_defaults_to_totals(tmp_path, monkeypatch, answers, expected):
    from cli import stock_processing_launcher as launcher
    from engine.stock_processing import generator

    monkeypatch.setattr(app_paths, "PROFILES_ROOT", tmp_path / "profiles")
    _profile(tmp_path, "")
    stock, price, output = tmp_path / "s.xlsx", tmp_path / "p.xlsx", tmp_path / "o.xlsx"
    pd.DataFrame({"SKU": ["R1"], "Local": [2]}).to_excel(stock, index=False)
    pd.DataFrame({"SKU": ["R1"], "Base": ["Local"], "Precio": [10.0]}).to_excel(price, index=False)
    files, replies, received = iter(map(str, (stock, price, price, output))), iter(answers), []
    monkeypatch.setattr(launcher, "ask_file", lambda *_args, **_kwargs: next(files))
    monkeypatch.setattr(launcher, "clear_screen", lambda: None)
    monkeypatch.setattr("builtins.input", lambda prompt="": next(replies) if "unit prices" in prompt else "")
    monkeypatch.setattr(generator, "run_stock_processing", lambda args: received.append(args.include_unit_prices))
    launcher.launch_stock_processing("report")
    assert received == [expected]


def test_unit_prices_never_overwrite_template_content(tmp_path, template):
    workbook = load_workbook(template)
    workbook["Base"]["F1"] = "nota"
    edited = tmp_path / "edited.xlsx"
    workbook.save(edited)
    with pytest.raises(ReportTemplateError):
        fill(edited, FRAME.assign(**{"PrecioUnit.Costo.Local": 1.0}))


@pytest.mark.parametrize("template, message", [("missing.xlsx", "not found"), ("../../outside.xlsx", "inside the profile")])
def test_invalid_template_stops_before_writing_output(tmp_path, monkeypatch, template, message):
    monkeypatch.setattr(app_paths, "PROFILES_ROOT", tmp_path / "profiles")
    _profile(tmp_path, template)
    with pytest.raises(ValueError, match=message):
        _run(tmp_path)
    assert not (tmp_path / "o.xlsx").exists()


def test_rejected_template_leaves_the_previous_report_untouched(tmp_path, monkeypatch):
    monkeypatch.setattr(app_paths, "PROFILES_ROOT", tmp_path / "profiles")
    root = _profile(tmp_path, "report.xlsx")
    build_template(root / "report.xlsx", data_sheet="Otra")
    (tmp_path / "o.xlsx").write_bytes(b"previous")
    with pytest.raises(ReportTemplateError, match="no 'Base' data sheet"):
        _run(tmp_path)
    assert (tmp_path / "o.xlsx").read_bytes() == b"previous"
