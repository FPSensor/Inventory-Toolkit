"""Profile-owned workflow selection, independent of setup completion."""
from core import paths
from core.profile_store import load_json, save_json
from core.setup_catalog import MODULE_LABELS
from core.workflow_errors import ErrorCode, WorkflowError


def enabled_modules(profile):
    metadata = load_json(str(paths.profile_root(profile) / "profile.json")) or {}
    selected = metadata.get("enabled_modules", list(MODULE_LABELS))
    if not isinstance(selected, list) or not selected or any(name not in MODULE_LABELS for name in selected):
        raise WorkflowError(ErrorCode.CONFIG_INVALID, "Select at least one known workflow in profile settings.")
    return tuple(name for name in MODULE_LABELS if name in selected)


def set_enabled_modules(profile, modules):
    selected = list(dict.fromkeys(modules))
    if not selected or any(name not in MODULE_LABELS for name in selected):
        raise ValueError("Choose at least one workflow.")
    path = paths.profile_root(profile) / "profile.json"
    metadata = load_json(str(path)) or {}
    metadata["enabled_modules"] = selected
    save_json(str(path), metadata)


def require_enabled(profile, module):
    if module not in enabled_modules(profile):
        raise WorkflowError(ErrorCode.MODULE_DISABLED,
            f"{MODULE_LABELS[module]} is disabled for this profile. Enable it in profile settings before running it.", module=module)
