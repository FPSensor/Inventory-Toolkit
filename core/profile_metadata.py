"""Profile metadata validation independent of configuration initialization."""
from core import paths
from core.configuration_errors import ConfigurationFileError
from core.json_documents import read_document
from core.setup_catalog import MODULE_LABELS


def validate_metadata(payload):
    if not isinstance(payload, dict):
        raise ValueError('Profile metadata must be a JSON object.')
    selected = payload.get('enabled_modules', list(MODULE_LABELS))
    if (not isinstance(selected, list) or not selected or
            any(not isinstance(name, str) or name not in MODULE_LABELS for name in selected)):
        raise ValueError('Select at least one known workflow in profile settings.')
    return payload


def read_metadata(profile):
    path = paths.profile_root(profile) / 'profile.json'
    try:
        payload = read_document(path)
    except FileNotFoundError:
        return {}
    try:
        return validate_metadata(payload)
    except ValueError as exc:
        raise ConfigurationFileError(path, str(exc)) from exc
