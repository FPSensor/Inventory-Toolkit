import pandas as pd
import pytest
from openpyxl import Workbook
from pydantic import ValidationError

from core.config_schemas import YoYReportsConfig
from engine.yoy_reports.generator import generate_sales_report
from engine.yoy_reports.metrics import configured_branches, resolve_metric_specs
from engine.yoy_reports.sheet_renderer import render_report_sheet
from engine.yoy_reports.excel_renderer import render_yoy_sales_excel
from engine.yoy_reports.stats import build_yoy_stats


def _config(*, metrics=None, annual_comparison=True, include_sizes=False, groups=None):
    return {
        "version": 3,
        "input": {
            "date_column": "Date",
            "quantity_column": "Units",
            "sales_column": "Amount",
            "grouping_column": "Category",
            "item_column": "SKU",
            "branch_column": "Branch",
            "size_column": "Size",
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
            "Category": ["Category A", "Category A", "Category B"],
            "SKU": ["001", "002", "130"],
            "Branch": ["A", "B", "A"],
            "Units": [2, 1, 3],
            "Amount": [200.50, 120.00, 450.25],
            "Size": ["M", "L", "42"],
            "Date": pd.to_datetime(["2026-01-05", "2026-01-06", "2026-01-07"]),
        }
    )
    previous = current.copy()
    previous["Date"] = previous["Date"] - pd.DateOffset(years=1)
    previous["Units"] = [1, 2, 2]
    previous["Amount"] = [90.00, 210.00, 300.00]
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
        ("units", "Units"),
        ("sales", "Amount"),
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
        "Category",
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
        "Category",
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
        pd.Timestamp("2025-01-01"), config, "Category", False,
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
    february["Date"] = pd.Timestamp("2026-02-05")
    current = pd.concat([current, february], ignore_index=True)
    previous_february = february.copy()
    previous_february["Date"] = pd.Timestamp("2025-02-05")
    previous = pd.concat([previous, previous_february], ignore_index=True)
    events = []

    render_yoy_sales_excel(
        str(tmp_path / "segmented.xlsx"), current, previous,
        pd.Timestamp("2026-01-01"), pd.Timestamp("2026-02-28"),
        pd.Timestamp("2025-01-01"), _config(), "Category", True,
        interactive=False, progress=events.append,
    )

    assert len(events) == 4  # Two months, the consolidated sheet, then saving.
    assert [event.completed for event in events] == [2] * 4
    assert [event.fraction for event in events] == sorted(set(event.fraction for event in events))
    assert events[0].fraction == 2 / 3
    assert events[-1].fraction < 1
    assert "Prepared 3 sheets" in events[-1].message


def test_yoy_stats_use_unique_branches_and_label_single_branch_groups():
    current, previous = _frames()
    config = _config(groups={"north": ["A", "B"], "single": ["A"]})
    lines = build_yoy_stats(
        current, previous, pd.Timestamp("2026-01-01"), pd.Timestamp("2026-01-31"), config,
    )

    assert "  Jan 2026: 770.75 vs 600.00 (+28.5%)" in lines
    assert "  North (2 branches): 770.75 vs 600.00 (+28.5%)" in lines
    assert any(line.startswith("  A: ") for line in lines)
    assert "Overall (2 unique branches): 770.75 vs 600.00 (+28.5%)" in lines
    assert "N/A (prior year is zero)" in build_yoy_stats(
        current, previous.iloc[0:0], pd.Timestamp("2026-01-01"), pd.Timestamp("2026-01-31"), config,
    )[-1]


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
        responses = iter(("f", "y", "", "2026-01-01", "2026-01-31", "n", comparison_answer, "", ""))
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
    stats = []

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
        "Category",
        False,
        True,
        "demo",
        progress=events.append,
        stats=stats.append,
    )

    assert captured["include_sizes"] is True
    assert [event.completed for event in events] == [0, 1, 2, 3]
    assert "comparison periods selected" in events[1].message
    assert "Overall (2 unique branches): 6 vs 5 (+20.0%)" in stats[0].render()


def test_size_labels_and_total_formula_use_configured_column():
    current, previous = _frames()
    config = _config(include_sizes=True)
    size_column = 'Dimension*?"'
    current = current.rename(columns={"Size": size_column})
    previous = previous.rename(columns={"Size": size_column})
    config["input"]["size_column"] = size_column
    workbook = Workbook()
    render_report_sheet(
        workbook.active, current, previous,
        pd.Timestamp("2026-01-01"), pd.Timestamp("2026-01-31"),
        pd.Timestamp("2025-01-01"), config, "Category", include_sizes=True,
    )
    values = _sheet_values(workbook.active)
    assert any(str(value).startswith(f"  {size_column}: ") for value in values)
    assert any('Dimension~*~?""*' in str(value) for value in values if str(value).startswith('=SUMIF'))


@pytest.mark.parametrize('configured', [['units'], ['sales'], ['units', 'sales']])
@pytest.mark.parametrize('include_sales', [False, True])
def test_interactive_metrics_are_opt_in_without_mutating_profile(configured, include_sales):
    from copy import deepcopy
    from engine.yoy_reports.metrics import select_run_metrics

    config = _config(metrics=configured)
    original = deepcopy(config)
    selected = select_run_metrics(config, include_sales)
    assert selected['output']['metrics'] == (['units', 'sales'] if include_sales else ['units'])
    assert config == original
    selected['input']['quantity_column'] = 'Changed'
    assert config == original


@pytest.mark.parametrize('answer,expected', [('', ['units']), ('n', ['units']), ('y', ['units', 'sales'])])
def test_cli_selects_only_requested_metric_columns(tmp_path, monkeypatch, answer, expected):
    from copy import deepcopy
    from cli.yoy_reports_launcher import launch_yoy_reports
    from core import paths as app_paths

    monkeypatch.setattr(app_paths, 'PROFILES_ROOT', tmp_path / 'profiles')
    config = _config()
    original = deepcopy(config)
    monkeypatch.setattr('cli.yoy_reports_launcher.ConfigurationManager',
        lambda **_kwargs: type('Manager', (), {'get_yoy_reports_config': lambda self: config})())
    monkeypatch.setattr('cli.yoy_reports_launcher.ask_file',
        lambda _message, _default, is_output=False: str(tmp_path / ('output.xlsx' if is_output else 'input.xlsx')))
    monkeypatch.setattr('cli.yoy_reports_launcher.pd.read_excel', lambda *_args, **_kwargs: pd.DataFrame())
    fields = []
    def choose(_file, configured, _defaults, _confirm):
        fields.extend(configured)
        return configured
    monkeypatch.setattr('cli.yoy_reports_launcher.choose_input_columns', choose)
    captured = []
    monkeypatch.setattr('engine.yoy_reports.generator.generate_sales_report',
        lambda _file, out, _start, _end, selected, *_args, **_kwargs: captured.append(selected) or out)
    responses = iter(('f', 'y', answer, '2026-10-01', '2026-10-04', 'y', '', ''))
    monkeypatch.setattr('builtins.input', lambda _prompt: next(responses))
    launch_yoy_reports('test')
    assert captured[0]['output']['metrics'] == expected
    assert ('sales_column' in fields) == (answer == 'y')
    assert 'quantity_column' in fields
    assert config == original


@pytest.mark.parametrize('segmented', [False, True])
@pytest.mark.parametrize('include_sales', [False, True])
def test_selected_metrics_keep_units_and_line_revenue_separate_on_every_sheet(tmp_path, segmented, include_sales):
    from openpyxl import load_workbook
    from engine.yoy_reports.metrics import select_run_metrics

    current, previous = _frames()
    current['Date'] = pd.to_datetime(['2026-09-02', '2026-10-02', '2026-10-03'])
    previous['Date'] = current['Date'] - pd.DateOffset(years=1)
    current['Amount'] = [300000, 400000, 500000]
    config = select_run_metrics(_config(), include_sales)
    path = tmp_path / 'selected.xlsx'
    render_yoy_sales_excel(str(path), current, previous,
        pd.Timestamp('2026-09-01'), pd.Timestamp('2026-10-04'),
        pd.Timestamp('2025-09-01'), config, 'Category', segmented, interactive=False)
    workbook = load_workbook(path)
    assert workbook.sheetnames == (['09-26', '10-26', 'Full Report'] if segmented else ['Sales'])
    for sheet in workbook:
        titles = [str(row[0].value) for row in sheet]
        assert sum(title.startswith('Units Sold from') for title in titles) == 1
        assert sum(title.startswith('Sales Amount from') for title in titles) == int(include_sales)
        assert sum(title.startswith('YoY Sales Amount Comparison') for title in titles) == int(include_sales)
    sheet = workbook['10-26'] if segmented else workbook['Sales']
    if include_sales:
        title_row = next(row[0].row for row in sheet if str(row[0].value).startswith('Sales Amount from'))
        first_data_row = title_row + 2
        # Branch B has one line of 400000 revenue. Quantity must not multiply it.
        assert sheet.cell(first_data_row, 3).value == 400000
    workbook.close()


def test_revenue_comparisons_use_sum_ratios_and_handle_zero_denominators():
    from engine.yoy_reports.comparison_renderer import render_yoy_comparison_blocks

    current, previous = _frames()
    current['Amount'] = [200, 50, 0]
    previous['Amount'] = [100, 100, 0]
    config = _config(metrics=['sales'])
    lines = build_yoy_stats(current, previous, pd.Timestamp('2026-01-01'), pd.Timestamp('2026-01-31'), config)
    # The combined change is +25%, not the average of +100% and -50%.
    assert 'Overall (2 unique branches): 250.00 vs 200.00 (+25.0%)' in lines
    worksheet = Workbook().active
    render_yoy_comparison_blocks(worksheet, current, previous,
        pd.Timestamp('2026-01-01'), pd.Timestamp('2026-01-31'), pd.Timestamp('2025-01-01'),
        'Category', 'Branch', 'Amount', config['groups'], 1,
        metric_label='Sales Amount', number_format='#,##0.00')
    row = 4
    assert worksheet.cell(row, 2).value == 100
    assert worksheet.cell(row, 3).value == 200
    assert worksheet.cell(row, 5).value == 100
    assert worksheet.cell(row, 6).value == 50
    assert worksheet.cell(row, 8).value == '=B4+E4'
    assert worksheet.cell(row, 9).value == '=C4+F4'
    assert worksheet.cell(row, 10).value == '=IF(H4=0, "N/A", (I4-H4)/H4)'
    totals = next(r[0].row for r in worksheet if r[0].value == 'Totals')
    assert worksheet.cell(totals, 10).value == f'=IF(H{totals}=0, "N/A", (I{totals}-H{totals})/H{totals})'
    assert worksheet.cell(row, 10).number_format == '0.00%'
    for current_value, previous_value, expected in [(0, 100, '-100.0%'), (10, 0, 'N/A (prior year is zero)'), (-50, 100, '-150.0%')]:
        one = current.iloc[[0]].copy(); one['Amount'] = current_value
        prior = previous.iloc[[0]].copy(); prior['Amount'] = previous_value
        assert expected in build_yoy_stats(one, prior, pd.Timestamp('2026-01-01'), pd.Timestamp('2026-01-31'), config)[-1]


def test_unset_revenue_column_has_a_stable_configuration_destination():
    from engine.yoy_reports.metrics import select_run_metrics
    from core.workflow_errors import WorkflowError, ErrorCode
    config = _config()
    config['input']['sales_column'] = ''
    assert select_run_metrics(config, False)['output']['metrics'] == ['units']
    with pytest.raises(WorkflowError) as error:
        select_run_metrics(config, True)
    assert error.value.code == ErrorCode.CONFIG_REQUIRED_FIELD
    assert error.value.step == 'yoy_period'
    assert error.value.field == 'input.sales_column'
