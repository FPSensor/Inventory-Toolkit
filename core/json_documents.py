"""Strict JSON and rollback-safe writes shared by profile services."""
import json
import os
from pathlib import Path
import tempfile

from core.configuration_errors import ConfigurationFileError


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def decode_document(payload, path):
    """Parse UTF-8 bytes consistently, including Windows UTF-8 BOM documents."""
    try:
        return json.loads(payload.decode('utf-8-sig'), object_pairs_hook=_unique_object,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"non-finite JSON value {value}")))
    except (ValueError, UnicodeError) as exc:
        raise ConfigurationFileError(path, f"invalid JSON: {exc}") from exc


def read_document(path):
    path = Path(path)
    try:
        payload = path.read_bytes()
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise ConfigurationFileError(path, f"could not be read: {exc}") from exc
    return decode_document(payload, path)


def write_documents(documents):
    """Serialize first, stage all files, and restore prior bytes on a write failure.

    Each replacement is atomic. This is not a multi-process transaction manager;
    callers must prevent simultaneous editing of the same profile.
    """
    encoded = {Path(path): (json.dumps(value, indent=4, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        for path, value in documents.items()}
    write_payloads(encoded)


def write_payloads(encoded):
    """Apply encoded bytes or explicit deletions (None) with rollback."""
    encoded = {Path(path): payload for path, payload in encoded.items()}
    if any(payload is not None and not isinstance(payload, bytes) for payload in encoded.values()):
        raise TypeError('Document payloads must be bytes or None for deletion.')
    staged, original, replaced = {}, {}, []
    try:
        for path, payload in encoded.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            original[path] = path.read_bytes() if path.exists() else None
            fd, name = tempfile.mkstemp(dir=path.parent, prefix=".profile-", suffix=".tmp")
            staged[path] = Path(name)
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload if payload is not None else b'')
                handle.flush()
                os.fsync(handle.fileno())
        for path, temporary in staged.items():
            if encoded[path] is None:
                path.unlink(missing_ok=True)
            else:
                os.replace(temporary, path)
            replaced.append(path)
    except OSError:
        for path in reversed(replaced):
            if original[path] is None:
                path.unlink(missing_ok=True)
            else:
                # Reuse the staged sibling path so restoration is also atomic.
                temporary = staged[path]
                temporary.write_bytes(original[path])
                os.replace(temporary, path)
        raise
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)
