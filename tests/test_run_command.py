"""Reports can run unattended, with an exit status and a readable result."""
import json

import pandas as pd
import pytest

from core.runtime import paths
from inventory_toolkit.__main__ import main
from tests.test_report_template import _profile
from workflows import stock


@pytest.fixture
def files(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path / "profiles")
    _profile(tmp_path, "")
    pd.DataFrame({"SKU": ["R1"], "Local": [2]}).to_excel(tmp_path / "stock.xlsx", index=False)
    pd.DataFrame({"SKU": ["R1"], "Base": ["Local"], "Precio": [10.0]}).to_excel(tmp_path / "price.xlsx", index=False)
    return {"stock": str(tmp_path / "stock.xlsx"), "cost": str(tmp_path / "price.xlsx"),
            "sales": str(tmp_path / "price.xlsx")}


def run(*arguments):
    return main(["run", *arguments])


def test_a_report_runs_with_explicit_files(files, tmp_path, capsys):
    options = [item for name, path in files.items() for item in (f"--{name}", path)]
    status = run("stock", "--profile", "report", *options, "--output", str(tmp_path / "out"), "--unit-prices", "--json")
    printed = json.loads(capsys.readouterr().out)
    assert status == 0 and printed["ok"] and printed["warnings"] == []
    assert "PrecioUnit.Costo.Local" in pd.read_excel(printed["output"], sheet_name="Base")


def test_the_last_selection_is_used_by_default(files, tmp_path, capsys):
    request = stock.StockRequest("report", output=str(tmp_path / "remembered.xlsx"), **files)
    stock.prepare(request, stock.check(request))
    assert run("stock", "--profile", "report") == 0
    assert capsys.readouterr().out.strip() == str(tmp_path / "remembered.xlsx")


def test_a_failure_has_a_status_and_a_stable_code(files, capsys):
    assert run("stock", "--profile", "report", "--json") == 1
    printed = json.loads(capsys.readouterr().out)
    assert printed == {"ok": False, "code": "INPUT_FILE_MISSING", "error": printed["error"]}
    assert run("stock", "--profile", "missing") == 1
    assert "Profile not found" in capsys.readouterr().err
    assert not (paths.PROFILES_ROOT / "missing").exists()


@pytest.mark.parametrize("arguments", [["stock"], ["yoy", "--profile", "report"], ["other"], ["stock", "--profile", "report", "--typo"]])
def test_usage_errors_are_not_ignored(arguments, files):
    with pytest.raises(SystemExit) as error:
        run(*arguments)
    assert error.value.code == 2


def test_missing_packages_explain_how_to_install_them(monkeypatch, capsys):
    import importlib.util

    import inventory_toolkit.__main__ as entry

    real = importlib.util.find_spec
    monkeypatch.setattr(entry.importlib.util, "find_spec", lambda name: None if name == "pandas" else real(name))
    assert entry.main(["--interface", "cli"]) == 1
    message = capsys.readouterr().err
    assert "not installed: pandas." in message and "Setup Environment.bat" in message
