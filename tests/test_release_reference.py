from pathlib import Path

from openpyxl import Workbook

from tools.release_reference import (
    _fixture_hash,
    _fixture_hash_candidates,
    _sha256_file,
    compare_workbooks,
    workbook_semantic_sha256,
)


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


def test_release_reference_ignores_equivalent_ooxml_serializer_syntax(tmp_path):
    import xml.etree.ElementTree as ET
    import zipfile

    expected = tmp_path / "expected.xlsx"
    alternate = tmp_path / "alternate_serializer.xlsx"
    _save_sample(expected)

    # Re-serialize OOXML through ElementTree. This intentionally changes
    # namespace prefixes/formatting in the same way that OpenPyXL's optional
    # lxml and stdlib XML backends can produce byte-different workbooks.
    with zipfile.ZipFile(expected, "r") as source, zipfile.ZipFile(alternate, "w") as target:
        for name in source.namelist():
            payload = source.read(name)
            if name.endswith((".xml", ".rels")):
                try:
                    payload = ET.tostring(
                        ET.fromstring(payload),
                        encoding="utf-8",
                        xml_declaration=True,
                    )
                except ET.ParseError:
                    pass
            target.writestr(name, payload)

    result = compare_workbooks(expected, alternate)

    assert result.matches
    assert result.differences == ()
    assert workbook_semantic_sha256(expected) == workbook_semantic_sha256(alternate)


def test_release_reference_ignores_unused_style_registry_noise(tmp_path):
    from openpyxl import load_workbook
    from openpyxl.styles import Font, NamedStyle

    expected = tmp_path / "expected.xlsx"
    actual = tmp_path / "actual.xlsx"
    _save_sample(expected)
    _save_sample(actual)

    workbook = load_workbook(actual)
    unused = NamedStyle(name="runtime_generated_unused_style")
    unused.font = Font(bold=True, color="00AA00")
    workbook.add_named_style(unused)
    workbook.save(actual)
    workbook.close()

    result = compare_workbooks(expected, actual)

    assert result.matches
    assert result.differences == ()


def test_release_reference_still_detects_real_style_change(tmp_path):
    from openpyxl import load_workbook
    from openpyxl.styles import Font

    expected = tmp_path / "expected.xlsx"
    actual = tmp_path / "actual.xlsx"
    _save_sample(expected)
    _save_sample(actual)

    workbook = load_workbook(actual)
    workbook["Demo"]["A1"].font = Font(bold=True, color="FF0000")
    workbook.save(actual)
    workbook.close()

    result = compare_workbooks(expected, actual)

    assert not result.matches
    assert any("effective cell style changed" in difference for difference in result.differences)

def test_json_fixture_fingerprint_is_semantic_and_line_ending_independent(tmp_path):
    lf_json = tmp_path / "lf.json"
    crlf_json = tmp_path / "crlf.json"
    lf_json.write_bytes(b'{\n  "b": 2,\n  "a": 1\n}\n')
    crlf_json.write_bytes(b'{\r\n  "a": 1,\r\n  "b": 2\r\n}\r\n')

    assert _fixture_hash(lf_json) == _fixture_hash(crlf_json)


def test_json_fixture_accepts_legacy_lf_raw_hash_on_crlf_checkout(tmp_path):
    lf_json = tmp_path / "fixture_lf.json"
    crlf_json = tmp_path / "fixture_crlf.json"
    lf_json.write_bytes(b'{\n    "version": 3,\n    "enabled": true\n}\n')
    crlf_json.write_bytes(lf_json.read_bytes().replace(b"\n", b"\r\n"))

    legacy_manifest_hash = _sha256_file(lf_json)

    assert legacy_manifest_hash != _sha256_file(crlf_json)
    assert legacy_manifest_hash in _fixture_hash_candidates(crlf_json)


def test_json_fixture_fingerprint_detects_semantic_change(tmp_path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text('{"version": 3, "enabled": true}\n', encoding="utf-8")
    second.write_text('{"version": 3, "enabled": false}\n', encoding="utf-8")

    assert _fixture_hash(first) != _fixture_hash(second)
