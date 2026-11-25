"""Verify monetary opt-in is captured before dispatching a GUI worker."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from core.runtime import paths
from gui import app


class Variable:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


@pytest.mark.parametrize('include_sales', [False, True])
@pytest.mark.parametrize('segmented', [False, True])
def test_gui_captures_sales_selection_and_requires_only_selected_columns(tmp_path, monkeypatch, include_sales, segmented):
    source = tmp_path / 'source.xlsx'
    source.touch()
    config = {
        'input': {'date_column': 'Date', 'branch_column': 'Branch', 'quantity_column': 'Units',
                  'sales_column': 'Amount', 'grouping_column': 'Category', 'item_column': 'SKU', 'variant_column': 'Size'},
        'output': {'metrics': ['units', 'sales'], 'annual_comparison': True, 'default_path': 'out.xlsx'},
        'groups': {'group': ['A']},
    }
    original = deepcopy(config)
    monkeypatch.setattr(paths, 'PROFILES_ROOT', tmp_path)
    monkeypatch.setattr('workflows.yoy.ConfigurationManager', lambda _profile, **_kwargs: SimpleNamespace(get_yoy_reports_config=lambda: config))
    monkeypatch.setattr(app.messagebox, 'showerror', lambda *_args, **_kwargs: pytest.fail('Unexpected GUI error'))
    selected_fields = []
    captured_tasks = []
    generated = []

    def select(_file, configured, _defaults, _confirm):
        selected_fields.extend(configured)
        return configured

    def generate(*args, **kwargs):
        generated.append(args[4])
        return 'out.xlsx'

    monkeypatch.setattr('engine.yoy_reports.generator.generate_sales_report', generate)
    monkeypatch.setattr('workflows.base.choose_input_columns', select)
    view = SimpleNamespace(
        _require_idle=lambda: True, _gate_setup=lambda _module: True,
        active_profile=Variable('test'), yoy_file=Variable(str(source)),
        yoy_start=Variable('2026-10-01'), yoy_end=Variable('2026-10-04'),
        yoy_group=Variable('Family'), yoy_has_fam=Variable(True),
        yoy_seg=Variable(segmented), yoy_compare=Variable(False), yoy_variants=Variable(False),
        yoy_sales_amounts=Variable(include_sales), yoy_out=Variable('out.xlsx'),
        _confirm_column=None, _handle_error=lambda exc: pytest.fail(str(exc)),
        _run_async=lambda task, _message: captured_tasks.append(task),
    )
    view._run_workflow = lambda *args: app.InventoryToolkitGUI._run_workflow(view, *args)
    app.InventoryToolkitGUI._exec_yoy(view)
    assert ('sales_column' in selected_fields) == include_sales
    assert 'quantity_column' in selected_fields
    assert len(captured_tasks) == 1
    # The worker must use the captured choice, without reading Tk variables.
    view.yoy_sales_amounts = None
    assert captured_tasks[0](None, None).output == 'out.xlsx'
    assert generated[0]['output']['metrics'] == (['units', 'sales'] if include_sales else ['units'])
    assert generated[0]['output']['annual_comparison'] is segmented
    assert config == original
