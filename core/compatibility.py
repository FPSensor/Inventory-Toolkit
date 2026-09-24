"""Runtime diagnostics for temporary compatibility paths.

Compatibility diagnostics are disabled by default so library/API consumers are
not spammed. The CLI enables them when ``-debug_level`` is 2 or 3. Warnings are
emitted at most once per compatibility event during a process lifetime.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from core.logger import log

_diagnostics_enabled = False
_emitted_events: set[tuple[str, ...]] = set()


def configure_compatibility_diagnostics(enabled: bool) -> None:
    """Enable or disable user-visible compatibility diagnostics."""
    global _diagnostics_enabled
    _diagnostics_enabled = bool(enabled)


def reset_compatibility_diagnostics() -> None:
    """Reset process-local diagnostic state (primarily useful for tests)."""
    global _diagnostics_enabled
    _diagnostics_enabled = False
    _emitted_events.clear()


def warn_legacy_api(profile: str, logical_name: str) -> None:
    """Warn when a caller requests a pre-v2 configuration projection."""
    event = ("api", profile, logical_name)
    if not _should_emit(event):
        return
    log.warning(
        "Deprecated configuration compatibility API used for profile '%s': "
        "get_config('%s'). Update the caller to the module-oriented English API "
        "before legacy compatibility is retired.",
        profile,
        logical_name,
    )


def warn_legacy_storage(configs_dir: Path, legacy_files: Iterable[str]) -> None:
    """Warn when active pre-v2 configuration files are found in a profile."""
    profile = _profile_name(configs_dir)
    files = tuple(sorted(set(legacy_files)))
    event = ("storage", profile, *files)
    if not _should_emit(event):
        return

    preview = ", ".join(files[:3])
    if len(files) > 3:
        preview += f", +{len(files) - 3} more"
    log.warning(
        "Deprecated legacy configuration storage detected for profile '%s' "
        "(%s). Migrate/archive it from Configuration -> "
        "Migrate/archive legacy config. This compatibility path will be removed.",
        profile,
        preview or "legacy files",
    )


def warn_modular_upgrade(configs_dir: Path, from_versions: Iterable[int]) -> None:
    """Warn when a pre-v3 modular profile needs compatibility translation."""
    profile = _profile_name(configs_dir)
    versions = tuple(sorted(set(int(version) for version in from_versions)))
    event = ("upgrade", profile, *(str(version) for version in versions))
    if not _should_emit(event):
        return
    rendered = ", ".join(f"v{version}" for version in versions) or "pre-v3"
    log.warning(
        "Deprecated modular configuration compatibility used for profile '%s' "
        "(%s -> current schema). Save/validate the profile with the current "
        "Configuration Hub before compatibility is retired.",
        profile,
        rendered,
    )


def _should_emit(event: tuple[str, ...]) -> bool:
    if not _diagnostics_enabled or event in _emitted_events:
        return False
    _emitted_events.add(event)
    return True


def _profile_name(configs_dir: Path) -> str:
    try:
        return configs_dir.resolve().parent.name
    except OSError:
        return configs_dir.parent.name or "unknown"
