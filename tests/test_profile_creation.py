import pytest

from core import paths
from core.configuration_manager import ConfigurationManager
from core.profile_creation import create_profile, profile_slug
from core.module_preferences import enabled_modules


def test_neutral_profile_creation_selects_workflows_without_company_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path)
    profile = create_profile("Example Market", "", ["stock_processing"])
    manager = ConfigurationManager(profile)
    assert manager.get_catalog_columns() == {"article": "SKU", "family": "Category"}
    assert manager.get_family_rules() == {}
    assert enabled_modules(profile) == ("stock_processing",)
    assert manager.get_stock_processing_config()["input"]["article_column"] == "SKU"
    with pytest.raises(FileExistsError):
        create_profile("Example Market", "", ["cross_check"])
    assert enabled_modules(profile) == ("stock_processing",)
    with pytest.raises(ValueError):
        create_profile("Invalid", "", [])
    assert not (tmp_path / "invalid").exists()
    with pytest.raises(ValueError):
        profile_slug("CON")
