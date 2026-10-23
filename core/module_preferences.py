"""Profile-owned workflow selection, independent of setup completion."""
from core import paths
from core.profile_store import save_json
from core.profile_metadata import read_metadata
from core.setup_catalog import MODULE_LABELS
from core.workflow_errors import ErrorCode, WorkflowError


def enabled_modules(profile):
    metadata = read_metadata(profile)
    selected = metadata.get("enabled_modules", list(MODULE_LABELS))
    return tuple(name for name in MODULE_LABELS if name in selected)


def set_enabled_modules(profile, modules):
    if not isinstance(modules, (list, tuple)) or not modules or any(not isinstance(name, str) or name not in MODULE_LABELS for name in modules):
        raise ValueError("Choose at least one workflow.")
    selected = list(dict.fromkeys(modules))
    if not selected:
        raise ValueError("Choose at least one workflow.")
    path = paths.profile_root(profile) / "profile.json"
    metadata = read_metadata(profile)
    metadata["enabled_modules"] = selected
    save_json(str(path), metadata)


def require_enabled(profile, module):
    if module not in enabled_modules(profile):
        raise WorkflowError(ErrorCode.MODULE_DISABLED,
            f"{MODULE_LABELS[module]} is disabled for this profile. Enable it in profile settings before running it.", module=module)
