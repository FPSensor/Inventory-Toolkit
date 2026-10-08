"""Embedded assistant and recovery behavior without a native display."""
from types import SimpleNamespace, MethodType

import pytest

from gui.app import InventoryToolkitGUI
from gui.setup_wizard import SetupWizard, table_value
from core import paths
from core.profile_config import ensure_profile_config
from core.setup_service import SetupSession, initialize_setup, write_json
from core.workflow_errors import WorkflowError, ErrorCode


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, 'PROFILES_ROOT', tmp_path / 'profiles')
    ensure_profile_config(paths.profile_configs_root('test'))
    write_json(paths.profile_root('test') / 'profile.json', {'name': 'Test'})
    initialize_setup('test')
    return SetupSession('test', 'cross_check')


def test_tables_do_not_require_json_or_accept_ambiguous_names():
    assert table_value('rules', [['Category', 'AB, ABC']]) == {'Category': ['AB', 'ABC']}
    assert table_value('mapping', [['Origin', 'Store']]) == {'Origin': 'Store'}
    assert table_value('summaries', [['Example', 'A,B', 'One,Two']]) == [
        {'sheet_name': 'Example', 'entities': ['A', 'B'], 'titles': ['One', 'Two']}]
    with pytest.raises(ValueError, match='more than once'):
        table_value('groups', [['Group', 'A'], ['Group', 'B']])
    with pytest.raises(ValueError, match='both'):
        table_value('mapping', [['Origin', '']])


def test_pausing_does_not_review_the_current_draft(session):
    messages = []
    view = SimpleNamespace(_loading=False, _closed=False, on_exit=messages.append)
    SetupWizard._leave(view)
    assert view._closed
    assert messages
    assert session.state() == 0


def test_failed_page_keeps_user_on_the_same_step(session):
    notices = []
    view = SimpleNamespace(_loading=False, session=session, index=0,
        _getters={'columns.article': lambda: '', 'columns.family': lambda: 'Category', 'default_family': lambda: 'Other'},
        notice=SimpleNamespace(configure=lambda **kw: notices.append(kw['text'])))
    assert not SetupWizard._save(view)
    assert view.index == 0
    assert session.state() == 0
    assert notices


def test_new_module_is_routed_to_embedded_setup_before_workflow(session):
    opened = []
    view = SimpleNamespace(active_profile=SimpleNamespace(get=lambda: 'test'),
        _open_wizard=opened.append, _partial_permission=None)
    assert not InventoryToolkitGUI._gate_setup(view, 'cross_check')
    assert opened == ['cross_check']


def test_partial_setup_offers_explicit_continue_and_configuration(session):
    from core.setup_catalog import get_value
    step = session.steps[0]
    session.save_step(step.id, {'.'.join(field.path): get_value(session.data(step), field.path) for field in step.fields})
    notifications = []
    view = SimpleNamespace(active_profile=SimpleNamespace(get=lambda: 'test'), _partial_permission=None,
        _notify=lambda *args: notifications.append(args), _open_wizard=lambda *_: None)
    assert not InventoryToolkitGUI._gate_setup(view, 'cross_check')
    actions = notifications[0][3]
    assert [label for label, _callback in actions] == ['Continue anyway', 'Complete setup']


def test_recovery_uses_codes_and_keeps_unrelated_failures_out_of_setup():
    notifications, opened = [], []
    view = SimpleNamespace(_notify=lambda *args: notifications.append(args),
        _open_wizard=lambda *args: opened.append(args))
    exc = WorkflowError(ErrorCode.CONFIG_REQUIRED_FIELD, 'Missing', module='yoy_reports', step='yoy_groups')
    InventoryToolkitGUI._handle_error(view, exc)
    notifications[-1][3][0][1]()
    assert opened == [('yoy_reports', 'yoy_groups')]
    InventoryToolkitGUI._handle_error(view, RuntimeError('Disk full'))
    assert notifications[-1][3] == []
    InventoryToolkitGUI._handle_error(view, WorkflowError(ErrorCode.INPUT_COLUMN_MISSING, 'Missing header'))
    assert notifications[-1][3] == []


def test_inline_notice_retains_message_without_a_dialog():
    stored = []
    view = SimpleNamespace(_feedback_text=SimpleNamespace(configure=lambda **kw: stored.append(kw['text'])),
        _feedback_actions=SimpleNamespace(winfo_children=lambda: []))
    InventoryToolkitGUI._notify(view, 'error', 'Example', 'Readable explanation')
    assert stored == ['Example: Readable explanation']


def test_family_conflicts_warn_only_for_equal_prefixes_in_distinct_families():
    from gui.setup_wizard import family_rule_warnings
    assert not family_rule_warnings({'First': ['AB'], 'Specific': ['ABC']})
    assert len(family_rule_warnings({'First': ['ABC'], 'Second': ['ABC']})) == 1
