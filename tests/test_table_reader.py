"""One reader turns every supported file into the same table."""
import pandas as pd
import pytest

from core.table_reader import parse_dates, read_headers, read_table

ROWS = {"Code": ["00012", "A-1"], "Qty": [1.5, 1000.0], "Name": ["Café", "Té"]}


def write(path, text, encoding="utf-8"):
    path.write_bytes(text.encode(encoding))
    return path


@pytest.mark.parametrize("name, text, encoding", [
    ("a.csv", "Code,Qty,Name\n00012,1.5,Café\nA-1,\"1,000\",Té\n", "utf-8"),
    ("b.csv", "Code;Qty;Name\r\n00012;1,5;Café\r\nA-1;1.000,0;Té\r\n", "cp1252"),
    ("c.tsv", "Code\tQty\tName\n00012\t1.5\tCafé\nA-1\t1000\tTé\n", "utf-8-sig"),
    ("d.txt", "Code|Qty|Name\n00012|1.5|Café\nA-1|1000|Té\n", "utf-8"),
])
def test_text_files_read_like_excel(tmp_path, name, text, encoding):
    pd.DataFrame(ROWS).to_excel(tmp_path / "x.xlsx", index=False)
    table = read_table(write(tmp_path / name, text, encoding), text=["Code"])
    expected = read_table(tmp_path / "x.xlsx", text=["Code"])
    assert table.astype(object).values.tolist() == expected.astype(object).values.tolist()
    assert read_headers(tmp_path / name) == list(ROWS)


def test_codes_with_leading_zeroes_are_never_numbers(tmp_path):
    table = read_table(write(tmp_path / "a.csv", "Code,Qty\n007,1\n12,2\n"))
    assert table["Code"].tolist() == ["007", "12"]


def test_columns_kept_as_stored_do_not_lose_a_localized_total(tmp_path):
    table = read_table(write(tmp_path / "a.csv", "Qty\n5\n1.5\n\"2,75x\"\n"), as_stored=["Qty"])
    assert table["Qty"].tolist() == [5, 1.5, "2,75x"]


def test_headerless_scanner_dumps(tmp_path):
    assert read_table(write(tmp_path / "scan.txt", "0012\n0012\nB\n"), header=False)[0].tolist() == ["0012", "0012", "B"]


def two_sheets(path, second):
    with pd.ExcelWriter(path) as book:
        pd.DataFrame({"A": [1]}).to_excel(book, sheet_name="2025", index=False)
        pd.DataFrame(second).to_excel(book, sheet_name="2026", index=False)
    return path


def test_other_sheets_with_the_same_columns_are_reported_or_joined(tmp_path):
    path, notices = two_sheets(tmp_path / "x.xlsx", {"A": [2]}), []
    assert read_table(path, on_notice=notices.append)["A"].tolist() == [1]
    assert len(notices) == 1 and "2026" in notices[0]
    assert read_table(path, all_sheets=True, on_notice=notices.append)["A"].tolist() == [1, 2]
    assert len(notices) == 1


def test_unrelated_sheets_are_ignored(tmp_path):
    notices = []
    path = two_sheets(tmp_path / "x.xlsx", {"Other": [2]})
    assert read_table(path, all_sheets=True, on_notice=notices.append)["A"].tolist() == [1] and notices == []


@pytest.mark.parametrize("name", ["a.pdf", "a.xlsx"])
def test_unreadable_files_are_explained(tmp_path, name):
    with pytest.raises(ValueError, match=name):
        read_table(write(tmp_path / name, "nothing"))


@pytest.mark.parametrize("values, expected", [
    (["25/10/2026", "01/02/2026"], ["2026-10-25", "2026-02-01"]),
    (["10/25/2026", "01/02/2026"], ["2026-10-25", "2026-01-02"]),
    (["2026-02-01", "2026-10-25 13:00"], ["2026-02-01", "2026-10-25"]),
    ([pd.Timestamp("2026-02-01"), "25-10-2026"], ["2026-02-01", "2026-10-25"]),
    (["2026-02-01", "Total", None], ["2026-02-01", "NaT", "NaT"]),
])
def test_day_and_month_order_comes_from_the_values(values, expected):
    assert [str(value)[:10] for value in parse_dates(pd.Series(values, dtype=object))] == expected


@pytest.mark.parametrize("values", [["01/02/2026", "03/04/2026"], ["25/10/2026", "10/25/2026"]])
def test_ambiguous_dates_are_not_guessed(values):
    with pytest.raises(ValueError, match="day"):
        parse_dates(pd.Series(values, dtype=object, name="Fecha"))
