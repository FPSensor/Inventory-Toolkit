"""Setup lifecycle uses synthetic profiles, never demo business rules."""
from copy import deepcopy
import json

import pytest

from core import paths
from core.profile_config import ensure_profile_config
from core.setup_catalog import STEPS, get_value
from core.setup_service import SetupSession, SetupState, initialize_setup, write_json
from core.workflow_errors import WorkflowError, ErrorCode


@pytest.fixture
def profile(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, 'PROFILES_ROOT', tmp_path / 'profiles')
    ensure_profile_config(paths.profile_configs_root('test'))
    write_json(paths.profile_root('test') / 'profile.json', {'name': 'Test', 'version': '1.4.1'})
    return 'test'


def values(session, step):
    return {'.'.join(field.path): deepcopy(get_value(session.data(step), field.path)) for field in step.fields}


def test_existing_profiles_are_not_forced_through_setup(profile):
    assert SetupSession(profile, 'cross_check').state() == SetupState.COMPLETE
    assert 'setup' not in json.loads((paths.profile_root(profile) / 'profile.json').read_text())


def test_new_profiles_save_and_resume_each_module_independently(profile):
    initialize_setup(profile)
    session = SetupSession(profile, 'cross_check')
    assert session.state() == SetupState.NOT_CONFIGURED
    session.save_step('catalog', values(session, session.steps[0]))
    assert SetupSession(profile, 'cross_check').state() == SetupState.PARTIAL
    assert session.first_pending() == 'classification'
    assert SetupSession(profile, 'stock_processing').state() == SetupState.NOT_CONFIGURED
    for step in session.steps[1:]:
        session.save_step(step.id, values(session, step))
    assert session.state() == SetupState.COMPLETE
    # A shared change in another module invalidates the previously reviewed step.
    other = SetupSession(profile, 'stock_processing')
    changed = values(other, other.steps[0]); changed['columns.article'] = 'Identifier'
    other.save_step('catalog', changed)
    assert session.state() == SetupState.PARTIAL
    assert session.first_pending() == 'catalog'


def test_invalid_step_does_not_overwrite_config_or_progress(profile):
    initialize_setup(profile)
    session = SetupSession(profile, 'cross_check')
    step = session.steps[0]
    before = session.data(step)
    changed = values(session, step); changed['columns.article'] = ''
    with pytest.raises(WorkflowError) as error:
        session.save_step(step.id, changed)
    assert error.value.code == ErrorCode.CONFIG_REQUIRED_FIELD
    assert error.value.can_configure
    assert error.value.step == 'catalog'
    assert session.data(step) == before
    assert session.state() == SetupState.NOT_CONFIGURED


def test_required_module_groups_have_an_actionable_destination(profile):
    initialize_setup(profile)
    session = SetupSession(profile, 'yoy_reports')
    with pytest.raises(WorkflowError) as error:
        session.validate_required()
    assert error.value.step == 'yoy_groups'
    assert error.value.field == 'groups'
    step = next(step for step in session.steps if step.id == 'yoy_groups')
    session.save_step(step.id, {'groups': {'Example': ['A']}})
    session.validate_required()


def test_setup_state_is_not_trusted_when_metadata_is_invalid(profile):
    path = paths.profile_root(profile) / 'profile.json'
    write_json(path, {'setup': {'version': 99}})
    with pytest.raises(WorkflowError) as error:
        SetupSession(profile, 'cross_check').state()
    assert error.value.code == ErrorCode.SETUP_STATE_INVALID
    assert not error.value.can_configure


def test_enrolling_an_existing_module_preserves_other_legacy_workflows(profile):
    session = SetupSession(profile, 'cross_check')
    step = session.steps[0]
    session.save_step(step.id, values(session, step))
    assert session.state() == SetupState.PARTIAL
    assert SetupSession(profile, 'stock_processing').state() == SetupState.COMPLETE
    assert SetupSession(profile, 'yoy_reports').state() == SetupState.COMPLETE


def test_corrupt_progress_cannot_change_config(profile):
    session = SetupSession(profile, 'cross_check')
    step = session.steps[0]
    before = session.data(step)
    write_json(paths.profile_root(profile) / 'profile.json', {'setup': {'version': 1, 'modules': {'cross_check': {'reviewed': {'catalog': 2}}}}})
    with pytest.raises(WorkflowError):
        session.save_step(step.id, values(session, step))
    assert session.data(step) == before


def test_numeric_normalization_does_not_make_saved_page_stale(profile):
    initialize_setup(profile)
    session = SetupSession(profile, 'cross_check', include_advanced=True)
    step = next(step for step in session.steps if step.id == 'cross_policy')
    data = values(session, step)
    data['reconciliation.quantity_tolerance'] = 0
    session.save_step(step.id, data)
    assert session.effective_reviews()[step.id] == session.fingerprint(step)
