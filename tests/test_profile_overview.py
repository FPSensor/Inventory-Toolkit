"""The shared overview reports review progress without changing the profile."""

from core import paths
from core.profile_config import ensure_profile_config
from core.profile_overview import inspect_profile
from core.setup_catalog import get_value
from core.setup_service import SetupSession, initialize_setup, write_json
from core.setup_service import SetupState


def test_new_profile_reports_independent_module_progress(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, 'PROFILES_ROOT', tmp_path / 'profiles')
    ensure_profile_config(paths.profile_configs_root('example'))
    write_json(paths.profile_root('example') / 'profile.json', {'name': 'Example'})
    initialize_setup('example')
    before = (paths.profile_root('example') / 'profile.json').read_bytes()
    initial = inspect_profile('example')
    assert all(entry.status == 'Not configured' and entry.reviewed == 0 for entry in initial)
    assert initial[0].pending_step == 'catalog'
    assert before == (paths.profile_root('example') / 'profile.json').read_bytes()

    session = SetupSession('example', 'cross_check')
    step = session.steps[0]
    session.save_step(step.id, {'.'.join(f.path): get_value(session.data(step), f.path) for f in step.fields})
    partial = inspect_profile('example')
    assert partial[0].status == 'Partially configured'
    assert partial[0].reviewed == 1
    assert partial[0].pending_step == 'families'
    assert partial[1].reviewed == 0


def test_existing_profile_reports_ready_without_enrolling_setup(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, 'PROFILES_ROOT', tmp_path / 'profiles')
    ensure_profile_config(paths.profile_configs_root('existing'))
    write_json(paths.profile_root('existing') / 'profile.json', {'name': 'Existing'})
    overview = inspect_profile('existing')
    assert all(entry.status == 'Ready' and entry.reviewed is None for entry in overview)


def test_console_inspection_uses_selected_yoy_options(monkeypatch):
    from types import SimpleNamespace
    from cli import profile_overview as cli
    from core.profile_overview import ModuleOverview

    entry = ModuleOverview('yoy_reports', 'YoY Reports', SetupState.COMPLETE, None, 8, None, ())
    monkeypatch.setattr(cli, 'inspect_profile', lambda _profile: (entry, entry, entry))
    monkeypatch.setattr(cli, 'clear_screen', lambda: None)
    monkeypatch.setattr(cli, 'load_last_paths', lambda _profile: {})
    monkeypatch.setattr(cli, 'input_default', lambda _profile, _saved, filename: filename)
    monkeypatch.setattr(cli, 'ConfigurationManager', lambda _profile: SimpleNamespace(
        get_yoy_reports_config=lambda: {'output': {'include_sizes': False}}))
    received = []
    monkeypatch.setattr(cli, 'inspect_workflow_inputs', lambda *args, **kwargs: (
        received.append(kwargs) or SimpleNamespace(render=lambda: 'Inspection complete')))
    answers = iter(('I3', 'f', 'n', 'y', 'n', '', ''))
    monkeypatch.setattr('builtins.input', lambda _prompt: next(answers))
    cli.show_profile_overview('example')
    assert received == [{'grouping': 'family', 'has_families': False,
        'include_sales': True, 'include_sizes': False}]
