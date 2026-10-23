import pytest

from core import json_documents
from core.configuration_errors import ConfigurationFileError


def test_duplicate_keys_and_nonfinite_values_are_not_silently_accepted(tmp_path):
    path = tmp_path / "profile.json"
    for text in ('{"input": {"column": "A", "column": "B"}}', '{"value": NaN}'):
        path.write_text(text)
        with pytest.raises(ConfigurationFileError, match="invalid JSON"):
            json_documents.read_document(path)


def test_failed_second_replacement_restores_configuration_and_metadata(tmp_path, monkeypatch):
    config, metadata = tmp_path / "settings.json", tmp_path / "profile.json"
    config.write_bytes(b'{"old": 1}\r\n')
    metadata.write_bytes(b'{"reviewed": false}\r\n')
    before = [config.read_bytes(), metadata.read_bytes()]
    replace = json_documents.os.replace
    calls = []
    def fail_second(source, target):
        calls.append(target)
        if len(calls) == 2:
            raise OSError("simulated replacement failure")
        return replace(source, target)
    monkeypatch.setattr(json_documents.os, "replace", fail_second)
    with pytest.raises(OSError, match="simulated"):
        json_documents.write_documents({config: {"new": 2}, metadata: {"reviewed": True}})
    assert [config.read_bytes(), metadata.read_bytes()] == before
    assert not list(tmp_path.glob("*.tmp"))


def test_windows_utf8_bom_is_accepted_with_strict_json_rules(tmp_path):
    path = tmp_path / 'settings.json'
    path.write_bytes(b'\xef\xbb\xbf{"version": 3}')
    assert json_documents.read_document(path) == {'version': 3}
    path.write_bytes(b'\xef\xbb\xbf{"version": 3, "version": 4}')
    with pytest.raises(ConfigurationFileError, match='duplicate JSON key'):
        json_documents.read_document(path)


def test_deletion_rolls_back_when_a_later_replacement_fails(tmp_path, monkeypatch):
    first, second = tmp_path / 'first.json', tmp_path / 'second.json'
    first.write_bytes(b'old first'); second.write_bytes(b'old second')
    replace = json_documents.os.replace
    calls = []
    def fail_once(source, target):
        calls.append(target)
        if len(calls) == 1:
            raise OSError('replacement failed')
        return replace(source, target)
    monkeypatch.setattr(json_documents.os, 'replace', fail_once)
    with pytest.raises(OSError):
        json_documents.write_payloads({first: None, second: b'new second'})
    assert first.read_bytes() == b'old first' and second.read_bytes() == b'old second'
