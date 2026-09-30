"""Load bundled data resources independently of the caller's working directory."""

import json
from pathlib import Path

from core.configuration_errors import ConfigurationError

RESOURCE_ROOT = Path(__file__).resolve().parent / "resources"


def load_resource(name: str) -> dict:
    path = RESOURCE_ROOT / name
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("expected a JSON object")
        return payload
    except (OSError, ValueError) as exc:
        raise ConfigurationError(f"Could not load bundled resource '{name}': {exc}") from exc
