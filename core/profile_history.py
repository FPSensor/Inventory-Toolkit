"""Local bounded configuration checkpoints; no workbooks or remembered paths."""
import base64
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
from uuid import uuid4

from core.configuration_manager import _CONFIG_MODELS
from core.json_documents import decode_document, read_document, write_documents, write_payloads
from core.profile_config import validate_config_header
from core.profile_diagnostics import profile_directory
from core.profile_metadata import validate_metadata
from core.setup_catalog import MODULE_LABELS

HISTORY_LIMIT = 10
_ID = re.compile(r'\d{8}T\d{12}Z-[0-9a-f]{12}')
_DOCUMENTS = ('profile.json', *(f'configs/{logical}.json' for logical in _CONFIG_MODELS))


def _history(profile):
    root = profile_directory(profile)
    if not root.is_dir():
        raise ValueError('The profile does not exist.')
    return root / '.history'


def list_checkpoints(profile):
    """Return newest-first checkpoint identifiers without loading their contents."""
    return tuple(sorted((path.stem for path in _history(profile).glob('*.json')
                         if _ID.fullmatch(path.stem)), reverse=True))


def checkpoint_info(profile, identifier):
    if not isinstance(identifier, str) or not _ID.fullmatch(identifier):
        raise ValueError('Choose a checkpoint from this profile history.')
    payload = read_document(_history(profile) / f'{identifier}.json')
    if not isinstance(payload, dict) or payload.get('profile') != profile:
        raise ValueError('Checkpoint metadata is invalid.')
    return {'id': identifier, 'created': str(payload.get('created', 'Unknown time')),
            'label': str(payload.get('label', 'Configuration checkpoint'))}


def create_checkpoint(profile, label='Manual checkpoint', *, allow_missing=False):
    root = profile_directory(profile)
    if not root.is_dir():
        raise ValueError('The profile does not exist.')
    documents = {}
    for name in _DOCUMENTS:
        try:
            content = (root / name).read_bytes()
        except FileNotFoundError:
            if not allow_missing:
                raise
            documents[name] = {'sha256': None, 'content': None}
            continue
        documents[name] = {'sha256': hashlib.sha256(content).hexdigest(),
                           'content': base64.b64encode(content).decode('ascii')}
    now = datetime.now(timezone.utc)
    identifier = now.strftime('%Y%m%dT%H%M%S%fZ') + '-' + uuid4().hex[:12]
    payload = {'format': 1, 'profile': profile, 'created': now.isoformat(),
               'label': str(label), 'documents': documents}
    write_documents({_history(profile) / f'{identifier}.json': payload})
    for stale in list_checkpoints(profile)[HISTORY_LIMIT:]:
        (_history(profile) / f'{stale}.json').unlink()
    return identifier


def _load_checkpoint(profile, identifier):
    if not isinstance(identifier, str) or not _ID.fullmatch(identifier):
        raise ValueError('Choose a checkpoint identifier from this profile history.')
    payload = read_document(_history(profile) / f'{identifier}.json')
    if (not isinstance(payload, dict) or type(payload.get('format')) is not int or payload['format'] != 1 or
            payload.get('profile') != profile or not isinstance(payload.get('documents'), dict) or
            set(payload['documents']) != set(_DOCUMENTS)):
        raise ValueError('Checkpoint has an unsupported format or document set.')
    raw = {}
    for name, entry in payload['documents'].items():
        if not isinstance(entry, dict):
            raise ValueError('Invalid checkpoint document.')
        try:
            content = base64.b64decode(entry['content'], validate=True)
            if hashlib.sha256(content).hexdigest() != entry['sha256']:
                raise ValueError('Checksum does not match.')
            # Validation must happen before any live profile file changes.
            raw[name] = content
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f'Checkpoint document {name!r} is damaged: {exc}') from exc
    metadata = validate_metadata(decode_document(raw['profile.json'], 'profile.json'))
    modules = metadata.get('enabled_modules', list(MODULE_LABELS))
    for logical, model in _CONFIG_MODELS.items():
        name = f'configs/{logical}.json'
        if logical.startswith('general/') or logical.split('/')[0] in modules:
            data = decode_document(raw[name], name)
            validate_config_header(Path(name), data)
            model.model_validate(data)
    return raw


def restore_checkpoint(profile, identifier):
    """Validate first, checkpoint current state, then replace the saved documents.

    Restores the exact saved bytes after validating enabled documents. Input files, last paths,
    archived legacy data and the history directory are never replaced.
    """
    documents = _load_checkpoint(profile, identifier)
    root = profile_directory(profile)
    safety = create_checkpoint(profile, f'Before restoring {identifier}', allow_missing=True)
    write_payloads({root / name: payload for name, payload in documents.items()})
    return safety
