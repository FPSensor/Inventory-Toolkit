"""Headless diagnostics and restore commands work without either frontend."""
import json
import sys

from core import paths
from core.profile_creation import create_profile
from core.profile_history import create_checkpoint
from inventory_toolkit.maintenance import main


def test_doctor_json_and_exit_codes_do_not_import_frontends(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(paths, 'PROFILES_ROOT', tmp_path)
    profile = create_profile('CLI check', '', ['cross_check'])
    monkeypatch.setitem(sys.modules, 'cli', None)
    monkeypatch.setitem(sys.modules, 'gui', None)
    assert main(['doctor', '--profile', profile, '--json']) == 0
    assert json.loads(capsys.readouterr().out)['healthy']
    assert main(['doctor', '--profile', 'missing', '--json']) == 1
    assert not json.loads(capsys.readouterr().out)['healthy']


def test_history_round_trip_requires_explicit_noninteractive_confirmation(tmp_path, monkeypatch, capsys):
    import pytest
    monkeypatch.setattr(paths, 'PROFILES_ROOT', tmp_path)
    profile = create_profile('CLI history', '', ['cross_check'])
    identifier = create_checkpoint(profile)
    assert main(['history', 'list', '--profile', profile]) == 0
    assert identifier in capsys.readouterr().out
    class NonInteractive:
        def isatty(self): return False
    monkeypatch.setattr(sys, 'stdin', NonInteractive())
    with pytest.raises(SystemExit) as error:
        main(['history', 'restore', '--profile', profile, '--checkpoint', identifier])
    assert error.value.code == 2
    assert main(['history', 'restore', '--profile', profile, '--checkpoint', identifier, '--yes']) == 0
    assert 'Previous state saved' in capsys.readouterr().out
