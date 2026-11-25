import pytest

from core.files.system_utils import (
    InvalidExcelOutputPathError,
    OutputFileLockedError,
    normalize_xlsx_output_path,
    safe_openpyxl_save,
    safe_pandas_to_excel,
)


class _LockedDataFrame:
    def to_excel(self, *args, **kwargs):
        raise PermissionError("locked")


class _LockedWorkbook:
    def save(self, *args, **kwargs):
        raise PermissionError("locked")


class _FlakyDataFrame:
    def __init__(self):
        self.paths = []

    def to_excel(self, path, **kwargs):
        self.paths.append(path)
        if len(self.paths) == 1:
            raise PermissionError("locked")


def test_safe_pandas_non_interactive_raises_instead_of_prompting(tmp_path):
    output = tmp_path / "locked.xlsx"
    with pytest.raises(OutputFileLockedError) as exc_info:
        safe_pandas_to_excel(_LockedDataFrame(), str(output))
    assert exc_info.value.filepath == str(output)


def test_safe_openpyxl_non_interactive_raises_instead_of_prompting(tmp_path):
    output = tmp_path / "locked.xlsx"
    with pytest.raises(OutputFileLockedError) as exc_info:
        safe_openpyxl_save(_LockedWorkbook(), str(output))
    assert exc_info.value.filepath == str(output)


def test_a_locked_report_can_be_retried_or_saved_as_a_copy(tmp_path):
    output = tmp_path / "report.xlsx"
    frame = _FlakyDataFrame()
    asked = []

    final_path = safe_pandas_to_excel(frame, str(output), on_locked=lambda path: asked.append(path) or True)
    assert asked == [str(output)]
    retried = _FlakyDataFrame()
    assert safe_pandas_to_excel(retried, str(output), on_locked=lambda _path: False) == str(output)
    assert retried.paths == [str(output)] * 2

    assert frame.paths == [str(output), str(tmp_path / "report_copy1.xlsx")]
    assert final_path == str(tmp_path / "report_copy1.xlsx")


def test_xlsx_output_path_contract_appends_missing_extension(tmp_path):
    target = tmp_path / "report"
    assert normalize_xlsx_output_path(target) == str(target) + ".xlsx"


def test_xlsx_output_path_warns_only_when_appending_extension():
    notices = []
    assert normalize_xlsx_output_path("report", notify=notices.append) == "report.xlsx"
    assert notices == ["No output extension detected; using report.xlsx"]
    assert normalize_xlsx_output_path("report.xlsx", notify=notices.append) == "report.xlsx"
    assert len(notices) == 1


def test_empty_output_uses_module_default_without_warning(tmp_path, monkeypatch):
    from core.runtime import paths
    from workflows.base import settle_output
    from workflows.stock import StockRequest

    monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path)
    messages = []
    settle = lambda value: settle_output(
        StockRequest("demo", "", "", "", value), "stock_processing", "report.xlsx", messages.append).output
    assert settle("  ") == "report.xlsx" and messages == []
    assert settle("other") == "other.xlsx" and len(messages) == 1


@pytest.mark.parametrize("suffix", [".xls", ".xlsm", ".csv", ".ods"])
def test_xlsx_output_path_contract_rejects_unsupported_extensions(tmp_path, suffix):
    with pytest.raises(InvalidExcelOutputPathError, match="must use the .xlsx format"):
        normalize_xlsx_output_path(tmp_path / f"report{suffix}")


def test_xlsx_output_path_contract_accepts_case_insensitive_xlsx(tmp_path):
    target = tmp_path / "REPORT.XLSX"
    assert normalize_xlsx_output_path(target) == str(target)


def test_safe_writer_rejects_xls_before_touching_dataframe(tmp_path):
    frame = _FlakyDataFrame()
    with pytest.raises(InvalidExcelOutputPathError):
        safe_pandas_to_excel(frame, str(tmp_path / "report.xls"))
    assert frame.paths == []
