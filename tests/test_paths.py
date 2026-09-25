from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from cli import profiles as cli_profiles
from cli.utils import load_last_paths, save_last_paths, validate_files_exist
from core import paths as app_paths
from core.configuration_manager import ConfigurationManager


def test_application_resource_roots_are_absolute_and_repo_anchored():
    assert app_paths.APPLICATION_ROOT.is_absolute()
    assert app_paths.PROFILES_ROOT == app_paths.APPLICATION_ROOT / "profiles"
    assert app_paths.EXAMPLES_ROOT == app_paths.APPLICATION_ROOT / "examples"
    assert app_paths.LOGS_ROOT == app_paths.APPLICATION_ROOT / "logs"
    assert app_paths.TOOLS_ROOT == app_paths.APPLICATION_ROOT / "tools"
    assert app_paths.RELEASE_REFERENCE_ROOT == app_paths.APPLICATION_ROOT / "tests" / "release_reference"


def test_configuration_manager_ignores_foreign_cwd(tmp_path, monkeypatch):
    foreign_cwd = tmp_path / "somewhere" / "unrelated"
    foreign_cwd.mkdir(parents=True)
    monkeypatch.chdir(foreign_cwd)

    config = ConfigurationManager("demo")

    assert config.base_dir == app_paths.PROFILES_ROOT / "demo" / "configs"
    assert config.get_default_family() == "Otro"
    assert not (foreign_cwd / "profiles").exists()


def test_profile_last_paths_storage_is_application_owned(tmp_path, monkeypatch):
    profiles_root = tmp_path / "application" / "profiles"
    foreign_cwd = tmp_path / "caller"
    foreign_cwd.mkdir()
    monkeypatch.setattr(app_paths, "PROFILES_ROOT", profiles_root)
    monkeypatch.chdir(foreign_cwd)

    save_last_paths("test", {"stock_processing": {"stock": "relative-input.xlsx"}})

    stored = profiles_root / "test" / "last_paths.json"
    assert stored.exists()
    assert load_last_paths("test")["stock_processing"]["stock"] == "relative-input.xlsx"
    assert not (foreign_cwd / "profiles").exists()


def test_user_relative_paths_still_follow_caller_cwd(tmp_path, monkeypatch):
    user_file = tmp_path / "relative-input.xlsx"
    user_file.write_bytes(b"placeholder")
    monkeypatch.chdir(tmp_path)

    assert validate_files_exist(["relative-input.xlsx"])


def test_cli_profile_discovery_is_application_owned(tmp_path, monkeypatch):
    profiles_root = tmp_path / "application" / "profiles"
    (profiles_root / "alpha").mkdir(parents=True)
    (profiles_root / "beta").mkdir()
    foreign_cwd = tmp_path / "caller"
    foreign_cwd.mkdir()
    monkeypatch.setattr(app_paths, "PROFILES_ROOT", profiles_root)
    monkeypatch.chdir(foreign_cwd)

    assert cli_profiles._list_profiles() == ["alpha", "beta"]
    assert not (foreign_cwd / "profiles").exists()


def test_cli_entrypoint_imports_cleanly_from_foreign_cwd(tmp_path):
    result = subprocess.run(
        [sys.executable, str(app_paths.APPLICATION_ROOT / "cli.py"), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Inventory Toolkit CLI" in result.stdout
    for app_dir in ("profiles", "logs", "examples", "tests", "tools"):
        assert not (tmp_path / app_dir).exists()
