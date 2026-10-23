"""Shared, validated profile persistence; independent of either interface."""
import json
from core.json_documents import read_document, write_documents
from pathlib import Path

from core.configuration_errors import ConfigurationFileError
from core.logger import log_debug_event
from core.paths import profile_root

_LAST_PATHS_FILE = "last_paths.json"

def _validate_profile_document(path: Path, payload) -> None:
    """Validate editor documents before they can be read or replace a profile file."""
    if "configs" not in path.parts:
        return
    logical = Path(*path.parts[path.parts.index("configs") + 1:]).with_suffix("").as_posix()
    from core.configuration_manager import _CONFIG_MODELS

    model = _CONFIG_MODELS.get(logical)
    if model is None:
        return
    try:
        model.model_validate(payload)
    except Exception as exc:
        raise ConfigurationFileError(path, f"invalid profile configuration: {exc}") from exc

def load_json(path: str):
    try:
        payload = read_document(path)
        _validate_profile_document(Path(path), payload)
        log_debug_event("json_loaded", path=path, payload_type=type(payload).__name__)
        return payload
    except FileNotFoundError:
        log_debug_event("json_missing", path=path)
        return None
    except json.JSONDecodeError as exc:
        raise ConfigurationFileError(
            Path(path), f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    except (OSError, UnicodeError) as exc:
        raise ConfigurationFileError(Path(path), f"could not be read: {exc}") from exc


def save_json(path: str, data) -> None:
    target = Path(path)
    if target.exists() and "configs" in target.parts:
        load_json(str(target))  # Never replace a corrupt or future-version profile.
    _validate_profile_document(target, data)
    try:
        write_documents({target: data})
        log_debug_event("json_saved", path=path, payload_type=type(data).__name__)
    except (OSError, TypeError, ValueError) as exc:
        raise ConfigurationFileError(target, f"could not be saved: {exc}") from exc


def load_last_paths(profile: str) -> dict:
    """Load the saved file paths for *profile*. Returns {} if none saved yet."""
    path = profile_root(profile) / _LAST_PATHS_FILE
    payload = load_json(str(path)) or {}
    log_debug_event("last_paths_loaded", profile=profile, path=path, sections=sorted(payload.keys()))
    return payload


def save_last_paths(profile: str, paths: dict) -> None:
    """Persist file paths for *profile* so the next run can pre-fill them."""
    path = profile_root(profile) / _LAST_PATHS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_last_paths(profile)
    existing.update(paths)
    save_json(str(path), existing)
    log_debug_event("last_paths_saved", profile=profile, path=path, sections=sorted(paths.keys()))
