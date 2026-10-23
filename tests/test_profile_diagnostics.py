"""Profile inspection must explain contradictions without repairing files."""
from pathlib import Path

from core import paths
from core.json_documents import read_document, write_documents
from core.profile_creation import create_profile
from core.profile_diagnostics import inspect_configuration


def _profile(tmp_path, monkeypatch, modules=('cross_check',)):
    monkeypatch.setattr(paths, 'PROFILES_ROOT', tmp_path)
    return create_profile('Check example', '', list(modules))


def test_diagnostics_are_read_only_and_ignore_disabled_modules(tmp_path, monkeypatch):
    profile = _profile(tmp_path, monkeypatch)
    disabled = paths.profile_configs_root(profile) / 'yoy_reports/settings.json'
    disabled.write_text('broken JSON')
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    report = inspect_configuration(profile)
    assert report.healthy
    assert len(report.checked) == 4
    assert report.as_dict()['healthy'] is True
    assert 'does not read input workbooks' in report.render()
    assert before == {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}


def test_missing_documents_are_reported_without_default_creation(tmp_path, monkeypatch):
    profile = _profile(tmp_path, monkeypatch)
    source = paths.profile_configs_root(profile) / 'cross_check/settings.json'
    source.unlink()
    report = inspect_configuration(profile)
    assert not report.healthy
    assert any(issue.code == 'CONFIG_DOCUMENT' and issue.document.endswith('cross_check/settings.json') for issue in report.issues)
    assert not source.exists()


def test_collision_has_a_recovery_destination(tmp_path, monkeypatch):
    profile = _profile(tmp_path, monkeypatch)
    path = paths.profile_configs_root(profile) / 'cross_check/settings.json'
    data = read_document(path)
    data['input']['quantity_column'] = data['input']['article_column']
    write_documents({path: data})
    report = inspect_configuration(profile)
    issue = next(issue for issue in report.issues if issue.code == 'COLUMN_COLLISION')
    assert (issue.module, issue.step) == ('cross_check', 'cross_input')


def test_stock_sheet_and_cleanup_contradictions_are_detected(tmp_path, monkeypatch):
    profile = _profile(tmp_path, monkeypatch, ('stock_processing',))
    network = paths.profile_configs_root(profile) / 'general/network.json'
    data = read_document(network); data['active'] = ['Counter']
    write_documents({network: data})
    path = paths.profile_configs_root(profile) / 'stock_processing/settings.json'
    data = read_document(path)
    data['pricing']['default_store'] = 'Counter'
    data['cleaning']['drop_columns'] = ['SKU']
    data['output']['summaries'] = [{'sheet_name': 'stock', 'entities': ['Missing'], 'titles': []}]
    write_documents({path: data})
    codes = {issue.code for issue in inspect_configuration(profile).issues}
    assert {'DROP_REQUIRED', 'SHEET_COLLISION', 'SUMMARY_LOCATIONS'} <= codes


def test_duplicate_prefix_is_a_warning_not_a_longest_prefix_error(tmp_path, monkeypatch):
    profile = _profile(tmp_path, monkeypatch)
    path = paths.profile_configs_root(profile) / 'general/families.json'
    write_documents({path: {'version': 3, 'rules': {'First': ['AB'], 'Second': ['AB'], 'Specific': ['ABC']}}})
    report = inspect_configuration(profile)
    assert report.healthy
    assert [issue.code for issue in report.issues] == ['PREFIX_CONFLICT']


def test_diagnostics_do_not_create_missing_profiles(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, 'PROFILES_ROOT', tmp_path)
    assert not inspect_configuration('missing').healthy
    assert not (tmp_path / 'missing').exists()
    assert not inspect_configuration('../outside').healthy


def test_revenue_only_diagnostics_do_not_require_unused_quantity_header(tmp_path, monkeypatch):
    profile = _profile(tmp_path, monkeypatch, ('yoy_reports',))
    path = paths.profile_configs_root(profile) / 'yoy_reports/settings.json'
    data = read_document(path)
    data['groups'] = {'Comparison': ['Main']}
    data['output']['metrics'] = ['sales']
    data['input']['quantity_column'] = ''
    write_documents({path: data})
    assert inspect_configuration(profile).healthy
