"""Console module gating consumes stable setup states and recovery targets."""
from types import SimpleNamespace

import pytest

from cli import workflow_setup
from core.workflow_errors import WorkflowError, ErrorCode


@pytest.mark.parametrize('state,answers,expected_runs,expected_setups', [
    (0, [], 0, 1), (1, ['y'], 1, 0), (1, ['n', 'y'], 0, 1),
    (1, ['n', 'n'], 0, 0), (2, [], 1, 0),
])
def test_module_gate_respects_setup_and_operator_decisions(monkeypatch, state, answers, expected_runs, expected_setups):
    launches, setups = [], []
    responses = iter(answers)
    monkeypatch.setattr('builtins.input', lambda _prompt: next(responses))
    monkeypatch.setattr(workflow_setup, 'SetupSession', lambda *_: SimpleNamespace(state=lambda: state, validate_required=lambda: None))
    monkeypatch.setattr(workflow_setup, 'run_module_setup', lambda *args: setups.append(args))
    workflow_setup.launch_configured('test', 'cross_check', launches.append)
    assert len(launches) == expected_runs
    assert len(setups) == expected_setups


def test_recovery_targets_the_missing_field_without_automatic_rerun(monkeypatch):
    setups = []
    error = WorkflowError(ErrorCode.CONFIG_REQUIRED_FIELD, 'Missing store group', module='yoy_reports', step='yoy_groups')
    monkeypatch.setattr(workflow_setup, 'SetupSession', lambda *_: SimpleNamespace(state=lambda: 1, validate_required=lambda: (_ for _ in ()).throw(error)))
    responses = iter(['y', 'y'])
    monkeypatch.setattr('builtins.input', lambda _prompt: next(responses))
    monkeypatch.setattr(workflow_setup, 'run_module_setup', lambda *args: setups.append(args))
    workflow_setup.launch_configured('test', 'yoy_reports', lambda _: pytest.fail('Missing requirement was ignored'))
    assert setups == [('test', 'yoy_reports', 'yoy_groups')]


def test_non_configuration_errors_do_not_offer_a_wizard(monkeypatch):
    monkeypatch.setattr('builtins.input', lambda _prompt: pytest.fail('Unexpected configuration prompt'))
    assert not workflow_setup.recover_configuration('test', RuntimeError('Cannot write file'))
    assert not workflow_setup.recover_configuration('test', WorkflowError(ErrorCode.INPUT_COLUMN_MISSING, 'Header absent'))
