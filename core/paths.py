"""Canonical Inventory Toolkit application paths.

Application-owned resources must never depend on the process current working
directory. User-supplied paths remain relative to the caller's CWD unless the
caller provides an absolute path.
"""

from __future__ import annotations

from pathlib import Path

APPLICATION_ROOT = Path(__file__).resolve().parents[1]
PROFILES_ROOT = APPLICATION_ROOT / "profiles"
EXAMPLES_ROOT = APPLICATION_ROOT / "examples"
LOGS_ROOT = APPLICATION_ROOT / "logs"
TOOLS_ROOT = APPLICATION_ROOT / "tools"
TESTS_ROOT = APPLICATION_ROOT / "tests"
RELEASE_REFERENCE_ROOT = TESTS_ROOT / "release_reference"


def profile_root(profile: str) -> Path:
    """Return the absolute application-owned directory for *profile*."""
    return PROFILES_ROOT / profile


def profile_configs_root(profile: str) -> Path:
    """Return the absolute config directory for *profile*."""
    return profile_root(profile) / "configs"


def demo_root() -> Path:
    """Return the absolute built-in demo fixture directory."""
    return EXAMPLES_ROOT / "demo"
