import pandas as pd
import pytest
from openpyxl import Workbook
from pydantic import ValidationError

from core.config_schemas import YoYReportsConfig
from engine.yoy_reports.generator import generate_sales_report
from engine.yoy_reports.metrics import configured_branches, resolve_metric_specs
from engine.yoy_reports.sheet_renderer import render_report_sheet
from engine.yoy_reports.excel_renderer import render_yoy_sales_excel


def _config(*, metrics=None, annual_comparison=True, include_sizes=False, groups=None):
    return {
        "version": 3,
        "input": {
            "date_column": "Fecha",
            "quantity_column": "Cantidad",
            "sales_column": "Monto",
            "grouping_column": "Familias",
            "item_column": "Articulo",
            "branch_column": "Base",
            "size_column": "Talle",
        },
        "output": {
            "default_path": "report.xlsx",
            "metrics": ["units", "sales"] if metrics is None else metrics,
            "annual_comparison": annual_comparison,
            "include_sizes": include_sizes,
        },
        "groups": groups if groups is not None else {"north": ["A", "B"]},
    }


def _frames():
    current = pd.DataFrame(
        {
            "Familias": ["Remeras", "Remeras", "Jeans"],
            "Articulo": ["001", "002", "130"],
            "Base": ["A", "B", "A"],
            "Cantidad": [2, 1, 3],
            "Monto": [200.50, 120.00, 450.25],
            "Talle": ["M", "L", "42"],
            "Fecha": pd.to_datetime(["2026-01-05", "2026-01-06", "2026-01-07"]),
        }
    )
    previous = current.copy()
    previous["Fecha"] = previous["Fecha"] - pd.DateOffset(years=1)
    previous["Cantidad"] = [1, 2, 2]
    previous["Monto"] = [90.00, 210.00, 300.00]
    return current, previous


def _sheet_values(worksheet):
    return [
        cell.value
        for row in worksheet.iter_rows()
        for cell in row
        if cell.value is not None
    ]


def test_yoy_metric_config_is_explicit_and_validated():
    config = YoYReportsConfig.model_validate(_config()).model_dump()
    specs = resolve_metric_specs(config)
    assert [(spec.key, spec.column) for spec in specs] == [
        ("units", "Cantidad"),
        ("sales", "Monto"),
    ]

    with pytest.raises(ValidationError):
        YoYReportsConfig.model_validate(_config(metrics=[]))
    with pytest.raises(ValidationError):
        YoYReportsConfig.model_validate(_config(metrics=["profit"]))


def test_yoy_rejects_empty_report_groups_before_rendering():
    with pytest.raises(ValueError, match="at least one non-empty report group"):
        configured_branches(_config(groups={}))
    with pytest.raises(ValueError, match="at least one non-empty report group"):
        configured_branches(_config(groups={"empty": []}))


def test_yoy_renders_configured_units_and_sales_metrics():
    current, previous = _frames()
    workbook = Workbook()
    worksheet = workbook.active
    config = _config(annual_comparison=False)

    render_report_sheet(
        worksheet,
        current,
        previous,
        pd.Timestamp("2026-01-01"),
        pd.Timestamp("2026-01-31"),
        pd.Timestamp("2025-01-01"),
        config,
        "Familias",
        include_sizes=False,
    )

    values = _sheet_values(worksheet)
    assert any(str(value).startswith("Units Sold from") for value in values)
    assert any(str(value).startswith("Sales Amount from") for value in values)
    assert not any(str(value).startswith("YoY ") for value in values)

    sales_cells = [
        cell
        for row in worksheet.iter_rows()
        for cell in row
        if cell.value in {200.50, 120.00, 450.25}
    ]
    assert sales_cells
    assert all(cell.number_format == "#,##0.00" for cell in sales_cells)


def test_yoy_annual_comparison_setting_controls_comparison_blocks():
    current, previous = _frames()
    workbook = Workbook()
    worksheet = workbook.active
    config = _config(annual_comparison=True)

    render_report_sheet(
        worksheet,
        current,
        previous,
        pd.Timestamp("2026-01-01"),
        pd.Timestamp("2026-01-31"),
        pd.Timestamp("2025-01-01"),
        config,
        "Familias",
    )

    values = [str(value) for value in _sheet_values(worksheet)]
    assert any(value.startswith("YoY Units Sold Comparison") for value in values)
    assert any(value.startswith("YoY Sales Amount Comparison") for value in values)


def test_full_report_can_omit_extra_annual_comparison_without_losing_metrics(tmp_path):
    from openpyxl import load_workbook

    current, previous = _frames()
    config = _config(annual_comparison=False)
    path = tmp_path / "full_report.xlsx"
    render_yoy_sales_excel(
        str(path), current, previous,
        pd.Timestamp("2026-01-01"), pd.Timestamp("2026-01-31"),
        pd.Timestamp("2025-01-01"), config, "Familias", False,
        interactive=False,
    )

    workbook = load_workbook(path, read_only=True)
    assert workbook.sheetnames == ["Sales"]
    titles = [row[0].value for row in workbook.active if row[0].value]
    assert any(str(title).startswith("Units Sold from") for title in titles)
    assert any(str(title).startswith("Sales Amount from") for title in titles)
    assert not any(str(title).startswith("YoY ") for title in titles)


def test_segmented_progress_advances_after_each_rendered_sheet(tmp_path):
    current, previous = _frames()
    february = current.iloc[[0]].copy()
    february["Fecha"] = pd.Timestamp("2026-02-05")
    current = pd.concat([current, february], ignore_index=True)
    previous_february = february.copy()
    previous_february["Fecha"] = pd.Timestamp("2025-02-05")
    previous = pd.concat([previous, previous_february], ignore_index=True)
    events = []

    render_yoy_sales_excel(
        str(tmp_path / "segmented.xlsx"), current, previous,
        pd.Timestamp("2026-01-01"), pd.Timestamp("2026-02-28"),
        pd.Timestamp("2025-01-01"), _config(), "Familias", True,
        interactive=False, progress=events.append,
    )

    assert len(events) == 4  # Two months, the consolidated sheet, then saving.
    assert [event.completed for event in events] == [2] * 4
    assert [event.fraction for event in events] == sorted(set(event.fraction for event in events))
    assert events[0].fraction == 2 / 3
    assert events[-1].fraction < 1
    assert "Prepared 3 sheets" in events[-1].message


def test_cli_full_report_comparison_is_opt_in_and_reuses_last_paths(tmp_path, monkeypatch):
    from cli.yoy_reports_launcher import launch_yoy_reports
    from core import paths as app_paths

    monkeypatch.setattr(app_paths, "PROFILES_ROOT", tmp_path / "profiles")
    config = _config(metrics=["units"], annual_comparison=True)
    monkeypatch.setattr(
        "cli.yoy_reports_launcher.ConfigurationManager",
        lambda profile: type("Manager", (), {"get_yoy_reports_config": lambda self: config})(),
    )
    monkeypatch.setattr(
        "cli.yoy_reports_launcher.pd.read_excel",
        lambda *_args, **_kwargs: pd.DataFrame(columns=config["input"].values()),
    )
    monkeypatch.setattr(
        "cli.yoy_reports_launcher.choose_input_columns",
        lambda _file, configured, _defaults, _confirm: configured,
    )
    requested_defaults = []

    def choose_file(message, default, is_output=False):
        requested_defaults.append((message, default))
        return default if default else "sales.xlsx"

    monkeypatch.setattr("cli.yoy_reports_launcher.ask_file", choose_file)
    comparisons = []

    def generate(_input, output, _start, _end, resolved, *_args, **_kwargs):
        comparisons.append(resolved["output"]["annual_comparison"])
        return output

    monkeypatch.setattr("engine.yoy_reports.generator.generate_sales_report", generate)
    for comparison_answer in ("", "y"):
        responses = iter(("f", "y", "2026-01-01", "2026-01-31", "n", comparison_answer, "", ""))
        monkeypatch.setattr("builtins.input", lambda _prompt: next(responses))
        launch_yoy_reports("test")

    assert comparisons == [False, True]
    assert requested_defaults[2] == ("Sales data file", "sales.xlsx")
    assert requested_defaults[3] == ("Output file", "report.xlsx")


def test_generate_sales_report_uses_profile_include_sizes_default(monkeypatch, tmp_path):
    current, previous = _frames()
    config = _config(metrics=["units"], include_sizes=True)
    captured = {}
    events = []

    def fake_process(*_args, **_kwargs):
        return current, previous, pd.Timestamp("2025-01-01")

    def fake_render(*args, **kwargs):
        captured["include_sizes"] = args[9]
        return str(tmp_path / "report.xlsx")

    monkeypatch.setattr("engine.yoy_reports.generator.process_sales_data", fake_process)
    monkeypatch.setattr("engine.yoy_reports.generator.render_yoy_sales_excel", fake_render)

    generate_sales_report(
        "input.xlsx",
        str(tmp_path / "report.xlsx"),
        pd.Timestamp("2026-01-01"),
        pd.Timestamp("2026-01-31"),
        config,
        "Familias",
        False,
        True,
        "demo",
        progress=events.append,
    )

    assert captured["include_sizes"] is True
    assert [event.completed for event in events] == [0, 1, 2, 3]
    assert "current-period rows" in events[1].message
