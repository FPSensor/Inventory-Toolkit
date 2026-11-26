"""The only place that opens input files.

Every workflow receives the same kind of table whatever the file format. What
cannot be read without guessing is reported instead of being assumed.
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

import pandas as pd

EXCEL_FORMATS = (".xlsx", ".xlsm", ".xls")
TEXT_FORMATS = (".csv", ".tsv", ".txt")
FILE_PATTERNS = " ".join(f"*{suffix}" for suffix in (*EXCEL_FORMATS, *TEXT_FORMATS))


def read_table(path, *, text=(), as_stored=(), header=True, rows=None, all_sheets=False, on_notice=None):
    """Read one table.

    ``text`` columns keep their characters, such as leading zeroes. ``as_stored``
    columns are not converted as a whole, so a localized total stays readable.
    Sheets that repeat the first one's headers are joined with ``all_sheets`` and
    reported through ``on_notice`` otherwise.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    try:
        if suffix in EXCEL_FORMATS:
            return _read_excel(path, text, as_stored, header, rows, all_sheets, on_notice)
        if suffix in TEXT_FORMATS:
            return _read_text(path, text, as_stored, header, rows)
    except FileNotFoundError:
        raise
    except Exception as exc:
        raise ValueError(f"Could not read '{path.name}': {exc}") from exc
    raise ValueError(f"'{path.name}' is not a supported file. Use {FILE_PATTERNS}.")


def read_headers(path) -> list[str]:
    return list(read_table(path, rows=0).columns)


# Excel ------------------------------------------------------------------
def _excel_engine():
    """Calamine reads workbooks about five times faster than openpyxl, with the same values."""
    try:
        import python_calamine  # noqa: F401
    except ImportError:
        return None
    # pandas reads with calamine since 2.2.
    major, minor = (int(part) for part in pd.__version__.split(".")[:2])
    return "calamine" if (major, minor) >= (2, 2) else None


def _read_excel(path, text, as_stored, header, rows, all_sheets, on_notice):
    types = {**{column: object for column in as_stored}, **{column: str for column in text}}
    options = {"dtype": types or None, "nrows": rows} if header else {"dtype": str, "header": None, "nrows": rows}
    with pd.ExcelFile(path, engine=_excel_engine()) as book:
        table = pd.read_excel(book, sheet_name=0, **options)
        if not header or rows is not None:
            return table
        repeated = [
            name for name in book.sheet_names[1:]
            if len(table.columns) and list(pd.read_excel(book, sheet_name=name, nrows=0).columns) == list(table.columns)
        ]
        if repeated and all_sheets:
            return pd.concat([table, *(pd.read_excel(book, sheet_name=name, **options) for name in repeated)], ignore_index=True)
    if repeated and on_notice:
        on_notice(
            f"'{path.name}' has other sheets with the same columns that were not read: "
            f"{', '.join(map(str, repeated))}.")
    return table


# Text -------------------------------------------------------------------
def _read_text(path, text, as_stored, header, rows):
    payload = path.read_bytes()
    try:
        content = payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        content = payload.decode("cp1252")
    first_line = content.split("\n", 1)[0]
    delimiter = max(",;\t|", key=first_line.count)
    # A semicolon is used where the comma is the decimal separator.
    decimal = "," if delimiter == ";" else "."
    table = pd.read_csv(
        io.StringIO(content), sep=delimiter, dtype=str, header=0 if header else None, nrows=rows,
        quoting=csv.QUOTE_MINIMAL, skip_blank_lines=True, keep_default_na=False, na_values=[""],
    )
    if not header:
        return table
    table.columns = [str(column).strip() for column in table.columns]
    for column in table.columns:
        if column in text:
            continue
        numbers = table[column].map(lambda value: _number(value, decimal), na_action="ignore")
        if column in as_stored:
            table[column] = numbers.astype(object)
        elif numbers.notna().any() and not numbers.map(lambda value: isinstance(value, str)).any():
            table[column] = pd.to_numeric(numbers)
    return table


def _number(value, decimal):
    thousands = "." if decimal == "," else ","
    pattern = rf"-?(?!0\d)(\d{{1,3}}({re.escape(thousands)}\d{{3}})+|\d+)({re.escape(decimal)}\d+)?"
    clean = value.strip()
    if not re.fullmatch(pattern, clean):
        return value
    clean = clean.replace(thousands, "").replace(decimal, ".")
    return float(clean) if "." in clean else int(clean)


# Dates ------------------------------------------------------------------
def parse_dates(values: pd.Series) -> pd.Series:
    """Read dates, deciding day/month order from the values themselves."""
    is_text = values.map(lambda value: isinstance(value, str)).astype(bool)
    if not is_text.any():
        return pd.to_datetime(values, errors="coerce")
    written = values[is_text].map(str.strip)
    unique = pd.Series(written.unique())
    parts = unique.str.extract(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})").dropna().astype(int)
    day_first, month_first = bool(parts[0].gt(12).any()), bool(parts[1].gt(12).any())
    if not parts.empty and day_first == month_first:
        raise ValueError(
            f"The dates in column '{values.name}' mix day and month order."
            if day_first else
            f"The dates in column '{values.name}' can be read as day/month or month/day. "
            "Export them as YYYY-MM-DD or as Excel dates.")
    read = dict(zip(unique, pd.to_datetime(unique, errors="coerce", format="mixed", dayfirst=day_first)))
    return pd.to_datetime(values.where(~is_text, written.map(read)), errors="coerce")
