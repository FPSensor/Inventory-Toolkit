import pytest

from core import paths
from core.configuration_manager import ConfigurationManager
from core.module_preferences import enabled_modules, set_enabled_modules
from core.profile_config import ensure_profile_config
from core.profile_overview import inspect_profile
from core.setup_service import SetupSession
from core.workflow_errors import WorkflowError, ErrorCode


def test_disabled_module_is_not_required_or_loaded(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path)
    root = paths.profile_configs_root("example")
    ensure_profile_config(root)
    set_enabled_modules("example", ["cross_check"])
    (root / "yoy_reports/settings.json").write_text("broken JSON")
    manager = ConfigurationManager("example", module="cross_check")
    assert manager.get_cross_check_config()["version"] == 3
    assert enabled_modules("example") == ("cross_check",)
    assert [entry.status for entry in inspect_profile("example")][1:] == ["Disabled", "Disabled"]
    with pytest.raises(WorkflowError) as error:
        SetupSession("example", "yoy_reports")
    assert error.value.code == ErrorCode.MODULE_DISABLED
    with pytest.raises(ValueError, match="at least one"):
        set_enabled_modules("example", [])
