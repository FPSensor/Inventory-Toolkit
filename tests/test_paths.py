from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from cli import profiles as cli_profiles
from cli import cross_check_launcher, stock_processing_launcher, yoy_reports_launcher
from cli.utils import input_default, load_last_paths, save_last_paths, validate_files_exist
from core import paths as app_paths
from core.configuration_manager import ConfigurationManager
from gui.app import InventoryToolkitGUI


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


def test_gui_yoy_restores_saved_paths_for_each_profile(tmp_path, monkeypatch):
    from types import SimpleNamespace

    class Variable:
        def __init__(self, value=None):
            self.value = value

        def get(self):
            return self.value

        def set(self, value):
            self.value = value

    monkeypatch.setattr(app_paths, "PROFILES_ROOT", tmp_path / "profiles")
    save_last_paths("first", {"yoy_reports": {"file": "sales.xlsx", "out": "report.xlsx"}})
    monkeypatch.setattr(
        "gui.app.ConfigurationManager",
        lambda _profile: SimpleNamespace(
            get_yoy_reports_config=lambda: {"output": {"default_path": "default.xlsx"}}
        ),
    )
    view = SimpleNamespace(
        active_profile=Variable("first"),
        yoy_file=Variable(),
        yoy_out=Variable(),
        yoy_sizes=Variable(),
        yoy_compare=Variable(),
    )

    InventoryToolkitGUI._apply_yoy_profile_defaults(view)
    assert (view.yoy_file.get(), view.yoy_out.get()) == ("sales.xlsx", "report.xlsx")

    view.active_profile.set("second")
    InventoryToolkitGUI._apply_yoy_profile_defaults(view)
    assert (view.yoy_file.get(), view.yoy_out.get()) == ("", "default.xlsx")


def test_user_relative_paths_still_follow_caller_cwd(tmp_path, monkeypatch):
    user_file = tmp_path / "relative-input.xlsx"
    user_file.write_bytes(b"placeholder")
    monkeypatch.chdir(tmp_path)

    assert validate_files_exist(["relative-input.xlsx"])


def test_cross_check_demo_prompts_resolve_bundled_inputs_from_foreign_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cross_check_launcher, "clear_screen", lambda: None)
    monkeypatch.setattr(cross_check_launcher, "load_last_paths", lambda _profile: {})
    offered = []

    def accept_default(_prompt, default):
        offered.append(default)
        return default

    monkeypatch.setattr(cross_check_launcher, "ask_file", accept_default)
    monkeypatch.setattr(cross_check_launcher, "validate_files_exist", lambda _paths: False)
    monkeypatch.setattr("builtins.input", lambda _prompt: "")

    cross_check_launcher.launch_cross_check("demo")

    assert len(offered) == 4
    assert all(Path(path).is_file() for path in offered)
    assert all(Path(path).parent == app_paths.demo_root() for path in offered)
    assert input_default("demo", "my-count.xlsx", "cross_check_physical_count.xlsx") == "my-count.xlsx"


def test_stock_demo_prompts_resolve_bundled_inputs_from_foreign_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(stock_processing_launcher, "clear_screen", lambda: None)
    monkeypatch.setattr(stock_processing_launcher, "load_last_paths", lambda _profile: {})
    offered = []

    def accept_default(_prompt, default):
        offered.append(default)
        return default

    monkeypatch.setattr(stock_processing_launcher, "ask_file", accept_default)
    monkeypatch.setattr(stock_processing_launcher, "validate_files_exist", lambda _paths: False)
    monkeypatch.setattr("builtins.input", lambda _prompt: "")

    stock_processing_launcher.launch_stock_processing("demo")

    assert len(offered) == 3
    assert all(Path(path).is_file() for path in offered)
    assert all(Path(path).parent == app_paths.demo_root() for path in offered)
    assert input_default("demo", "custom-stock.xlsx", "stock_processing_raw_stock.xlsx") == "custom-stock.xlsx"


def test_yoy_demo_prompt_resolves_bundled_input_from_foreign_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(yoy_reports_launcher, "load_last_paths", lambda _profile: {})
    monkeypatch.setattr(yoy_reports_launcher, "save_last_paths", lambda *_args: None)
    offered = []

    def accept_default(_prompt, default):
        offered.append(default)
        return default

    monkeypatch.setattr(yoy_reports_launcher, "ask_file", accept_default)
    def reject_header(*_args, **_kwargs):
        raise ValueError("stop after selecting input")

    monkeypatch.setattr(yoy_reports_launcher.pd, "read_excel", reject_header)
    responses = iter(("i", ""))
    monkeypatch.setattr("builtins.input", lambda _prompt: next(responses))

    yoy_reports_launcher.launch_yoy_reports("demo")

    assert len(offered) == 1
    assert Path(offered[0]).is_file()
    assert Path(offered[0]).parent == app_paths.demo_root()
    assert input_default("demo", "custom-sales.xlsx", "yoy_sales_history.xlsx") == "custom-sales.xlsx"


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
