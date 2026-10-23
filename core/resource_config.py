"""Load bundled data resources independently of the caller's working directory."""

import json
from pathlib import Path

from core.configuration_errors import ConfigurationError
from core.json_documents import read_document

RESOURCE_ROOT = Path(__file__).resolve().parent / "resources"


def load_resource(name: str) -> dict:
    path = RESOURCE_ROOT / name
    try:
        payload = read_document(path)
        if not isinstance(payload, dict):
            raise ValueError("expected a JSON object")
        return payload
    except (OSError, ValueError) as exc:
        raise ConfigurationError(f"Could not load bundled resource '{name}': {exc}") from exc
