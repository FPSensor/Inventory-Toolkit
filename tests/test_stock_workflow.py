"""The Stock workflow prepares and runs the same way for every interface."""
import json

import pandas as pd
import pytest

from core import paths as app_paths
from core.profile_store import load_last_paths
from core.system_utils import InvalidExcelOutputPathError
from core.workflow_errors import ErrorCode, WorkflowError
from engine.stock_processing import generator
from tests.test_report_template import _profile
from workflows import stock


@pytest.fixture
def request_(tmp_path, monkeypatch):
    monkeypatch.setattr(app_paths, "PROFILES_ROOT", tmp_path / "profiles")
    _profile(tmp_path, "")
    files = {name: str(tmp_path / f"{name}.xlsx") for name in ("stock", "cost", "sales")}
    pd.DataFrame({"SKU": ["R1"], "Local": [2]}).to_excel(files["stock"], index=False)
    for name in ("cost", "sales"):
        pd.DataFrame({"SKU": ["R1"], "Base": ["Local"], "Precio": [10.0]}).to_excel(files[name], index=False)
    return stock.StockRequest("report", output=str(tmp_path / "out"), **files)


def test_a_request_becomes_a_report(request_, tmp_path):
    events, totals = [], []
    job = stock.prepare(request_, stock.check(request_))
    result = job.run(progress=events.append, stats=totals.append)
    assert result.output == str(tmp_path / "out.xlsx") and result.elapsed >= 0
    assert pd.read_excel(result.output, sheet_name="Base")["Local.Costo"].tolist() == [20]
    assert events[-1].fraction == 1 and len(totals) == 1
    assert load_last_paths("report")["stock_processing"]["out"] == result.output


def test_every_missing_file_is_named(request_, tmp_path):
    with pytest.raises(WorkflowError) as error:
        stock.check(stock.StockRequest("report", "", request_.cost, str(tmp_path / "no.xlsx")))
    assert error.value.code is ErrorCode.INPUT_FILE_MISSING
    assert "Raw stock: (not selected)" in str(error.value) and "Sales list" in str(error.value)
    assert "Cost list" not in str(error.value)


def test_the_interface_decides_about_a_default_column(request_):
    pd.DataFrame({"Artículo": ["R1"], "Base": ["Local"], "Precio": [1.0]}).to_excel(request_.cost, index=False)
    asked = []
    with pytest.raises(WorkflowError) as error:
        stock.check(request_, lambda *question: asked.append(question))
    assert error.value.code is ErrorCode.INPUT_COLUMN_MISSING
    assert asked == [(request_.cost, "article", "SKU", "Artículo")]
    assert stock.check(request_, lambda *_question: True)["cost"]["article"] == "Artículo"


def test_an_invalid_output_is_rejected_before_remembering_it(request_):
    from dataclasses import replace

    with pytest.raises(InvalidExcelOutputPathError):
        stock.prepare(replace(request_, output="report.xls"), {})
    assert "out" not in load_last_paths("report").get("stock_processing", {})


def test_warnings_are_returned_instead_of_printed(request_, tmp_path, capsys):
    path = tmp_path / "profiles" / "report" / "configs" / "stock_processing" / "settings.json"
    settings = json.loads(path.read_text(encoding="utf-8"))
    settings["output"]["hidden_families"] = ["Remeras"]
    path.write_text(json.dumps(settings), encoding="utf-8")
    result = stock.prepare(request_, stock.check(request_)).run()
    assert len(result.warnings) == 1 and "Remeras: 2 units" in result.warnings[0]
    assert "Remeras" not in capsys.readouterr().out


def test_a_run_without_report_is_an_error(request_, monkeypatch):
    monkeypatch.setattr(generator, "run_stock_processing", lambda _args: None)
    with pytest.raises(WorkflowError) as error:
        stock.prepare(request_, stock.check(request_)).run()
    assert error.value.code is ErrorCode.REPORT_NOT_CREATED
