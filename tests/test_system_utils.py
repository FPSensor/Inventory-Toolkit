import pytest

from core.system_utils import (
    OutputFileLockedError,
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
        safe_pandas_to_excel(_LockedDataFrame(), str(output), interactive=False)
    assert exc_info.value.filepath == str(output)


def test_safe_openpyxl_non_interactive_raises_instead_of_prompting(tmp_path):
    output = tmp_path / "locked.xlsx"
    with pytest.raises(OutputFileLockedError) as exc_info:
        safe_openpyxl_save(_LockedWorkbook(), str(output), interactive=False)
    assert exc_info.value.filepath == str(output)


def test_safe_pandas_cli_copy_behavior_is_preserved(tmp_path, monkeypatch):
    output = tmp_path / "report.xlsx"
    frame = _FlakyDataFrame()
    monkeypatch.setattr("builtins.input", lambda _prompt: "C")

    final_path = safe_pandas_to_excel(frame, str(output))

    assert frame.paths == [str(output), str(tmp_path / "report_copy1.xlsx")]
    assert final_path == str(tmp_path / "report_copy1.xlsx")
