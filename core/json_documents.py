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


def read_document(path):
    path = Path(path)
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"non-finite JSON value {value}")))
    except FileNotFoundError:
        raise
    except ValueError as exc:
        raise ConfigurationFileError(path, f"invalid JSON: {exc}") from exc
    except (OSError, UnicodeError) as exc:
        raise ConfigurationFileError(path, f"could not be read: {exc}") from exc


def write_documents(documents):
    """Serialize first, stage all files, and restore prior bytes on a write failure.

    Each replacement is atomic. This is not a multi-process transaction manager;
    callers must prevent simultaneous editing of the same profile.
    """
    encoded = {Path(path): (json.dumps(value, indent=4, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        for path, value in documents.items()}
    staged, original, replaced = {}, {}, []
    try:
        for path, payload in encoded.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            original[path] = path.read_bytes() if path.exists() else None
            fd, name = tempfile.mkstemp(dir=path.parent, prefix=".profile-", suffix=".tmp")
            staged[path] = Path(name)
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        for path, temporary in staged.items():
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
