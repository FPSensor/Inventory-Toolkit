"""Configuration-specific exceptions for fail-closed profile handling."""

from __future__ import annotations

from pathlib import Path


class ConfigurationError(ValueError):
    """Base error for profile configuration that cannot be used safely."""


class ConfigurationFileError(ConfigurationError):
    """Raised when an existing configuration file cannot be read as intended."""

    def __init__(self, path: str | Path, reason: str):
        self.path = Path(path)
        self.reason = reason
        super().__init__(f"Invalid configuration file '{self.path}': {reason}")
