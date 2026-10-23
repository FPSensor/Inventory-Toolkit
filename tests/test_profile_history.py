"""Configuration checkpoints must preserve bytes and validate before restore."""
import json

import pytest

from core import paths
from core.json_documents import read_document, write_documents
from core.profile_creation import create_profile
from core import profile_history as history


@pytest.fixture
def profile(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, 'PROFILES_ROOT', tmp_path)
    return create_profile('History test', '', ['cross_check'])


def test_restore_recovers_exact_bytes_and_retains_current_state(profile):
    root = paths.profile_root(profile)
    target = root / 'configs/cross_check/settings.json'
    original = target.read_bytes().replace(b'\n', b'\r\n')
    target.write_bytes(original)
    last = root / 'last_paths.json'; last.write_text('{"custom": {"file": "local.xlsx"}}')
    checkpoint = history.create_checkpoint(profile)
    data = read_document(target); data['input']['quantity_column'] = 'Changed'
    write_documents({target: data})
    changed = target.read_bytes()
    safety = history.restore_checkpoint(profile, checkpoint)
    assert target.read_bytes() == original
    assert 'local.xlsx' in last.read_text()
    assert safety in history.list_checkpoints(profile)
    history.restore_checkpoint(profile, safety)
    assert target.read_bytes() == changed


def test_damaged_snapshot_cannot_change_live_profile(profile):
    root = paths.profile_root(profile)
    checkpoint = history.create_checkpoint(profile)
    path = root / '.history' / f'{checkpoint}.json'
    data = read_document(path)
    data['documents']['profile.json']['sha256'] = 'broken'
    write_documents({path: data})
    before = (root / 'profile.json').read_bytes()
    with pytest.raises(ValueError, match='damaged'):
        history.restore_checkpoint(profile, checkpoint)
    assert (root / 'profile.json').read_bytes() == before
    assert len(history.list_checkpoints(profile)) == 1


def test_missing_live_document_can_be_recovered(profile):
    target = paths.profile_configs_root(profile) / 'cross_check/settings.json'
    original = target.read_bytes()
    checkpoint = history.create_checkpoint(profile)
    target.unlink()
    history.restore_checkpoint(profile, checkpoint)
    assert target.read_bytes() == original


def test_retention_and_path_ownership(profile, monkeypatch):
    monkeypatch.setattr(history, 'HISTORY_LIMIT', 3)
    for _ in range(5):
        latest = history.create_checkpoint(profile)
    assert len(history.list_checkpoints(profile)) == 3
    assert latest in history.list_checkpoints(profile)
    with pytest.raises(ValueError):
        history.restore_checkpoint(profile, '../profile')
    with pytest.raises(ValueError):
        history.create_checkpoint('../outside')


def test_restore_preserves_disabled_invalid_settings(profile):
    target = paths.profile_configs_root(profile) / 'yoy_reports/settings.json'
    target.write_bytes(b'not JSON')
    checkpoint = history.create_checkpoint(profile)
    target.write_bytes(b'other disabled data')
    history.restore_checkpoint(profile, checkpoint)
    assert target.read_bytes() == b'not JSON'
