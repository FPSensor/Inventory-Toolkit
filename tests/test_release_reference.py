from pathlib import Path

from openpyxl import Workbook

from tools.release_reference import compare_workbooks, workbook_semantic_sha256


def _save_sample(path: Path, value="=1+1", *, freeze="A2") -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Demo"
    sheet["A1"] = "Header"
    sheet["A2"] = value
    sheet.freeze_panes = freeze
    sheet.auto_filter.ref = "A1:A2"
    sheet.column_dimensions["A"].width = 18
    workbook.save(path)
    workbook.close()


def test_release_reference_matches_equivalent_workbooks(tmp_path):
    expected = tmp_path / "expected.xlsx"
    actual = tmp_path / "actual.xlsx"
    _save_sample(expected)
    _save_sample(actual)

    result = compare_workbooks(expected, actual)

    assert result.matches
    assert result.differences == ()
    assert workbook_semantic_sha256(expected) == workbook_semantic_sha256(actual)


def test_release_reference_reports_cell_level_difference(tmp_path):
    expected = tmp_path / "expected.xlsx"
    actual = tmp_path / "actual.xlsx"
    _save_sample(expected, "=1+1")
    _save_sample(actual, "=1+2")

    result = compare_workbooks(expected, actual)

    assert not result.matches
    assert any("Demo!A2" in difference for difference in result.differences)
    assert any("'=1+1'" in difference and "'=1+2'" in difference for difference in result.differences)


def test_release_reference_reports_presentation_difference(tmp_path):
    expected = tmp_path / "expected.xlsx"
    actual = tmp_path / "actual.xlsx"
    _save_sample(expected, freeze="A2")
    _save_sample(actual, freeze="B2")

    result = compare_workbooks(expected, actual)

    assert not result.matches
    assert any("freeze_panes" in difference for difference in result.differences)


def test_release_reference_ignores_xlsx_zip_timestamps(tmp_path):
    import zipfile

    expected = tmp_path / "expected.xlsx"
    repacked = tmp_path / "repacked.xlsx"
    _save_sample(expected)

    with zipfile.ZipFile(expected, "r") as source, zipfile.ZipFile(repacked, "w") as target:
        for name in source.namelist():
            info = zipfile.ZipInfo(name)
            info.date_time = (2030, 1, 2, 3, 4, 6)
            info.compress_type = zipfile.ZIP_DEFLATED
            target.writestr(info, source.read(name))

    result = compare_workbooks(expected, repacked)

    assert result.matches
    assert workbook_semantic_sha256(expected) == workbook_semantic_sha256(repacked)
