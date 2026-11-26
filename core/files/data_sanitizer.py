import re

import pandas as pd

_AMBIGUOUS_NUMBER = re.compile(r"[+-]?[1-9]\d{0,2}[.,]\d{3}")
_GROUPED_INTEGER = re.compile(r"[+-]?\d{1,3}(?:([.,])\d{3})(?:\1\d{3})+")


def clean_sku_series(series: pd.Series) -> pd.Series:
    """
    Normalizes article codes, removes trailing '.0' from numeric float conversions,
    strips unwanted whitespace, and safely converts NaN/None to empty strings.
    """
    if series.empty:
        return series
    return (
        series.fillna("")
        .astype(str)
        .str.strip()
        .str.replace(r'\.0$', '', regex=True)
        .replace(['nan', 'None', '<NA>', 'NAN'], '')
    )

def normalize_article_codes(series: pd.Series) -> pd.Series:
    """Return the article key shared by stock, scanner readings and price lists.

    Case is not meaningful in an article code, so ``abc-1`` and ``ABC-1`` are
    the same article everywhere.
    """
    return clean_sku_series(series).astype(str).str.upper()


def _rewrite_number(text: str) -> str:
    """Rewrite a local-format number using a dot as the only separator."""
    if _GROUPED_INTEGER.fullmatch(text):
        return text.replace(".", "").replace(",", "")
    if "." in text and "," in text:
        decimal = max(".", ",", key=text.rfind)
        thousands = "," if decimal == "." else "."
        return text.replace(thousands, "").replace(decimal, ".")
    return text.replace(",", ".")


def parse_numbers(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Read numbers written in any local format.

    Returns the values and the cells whose reading is a guess. Blank cells are
    zero and unreadable text is NaN. Text such as ``1.234`` may mean 1234 or
    1.234 depending on the source; it keeps the decimal reading and is marked.
    """
    if pd.api.types.is_numeric_dtype(series):
        return series.fillna(0), pd.Series(False, index=series.index)
    is_text = series.map(lambda value: isinstance(value, str)).astype(bool)
    text = series.where(is_text, "").astype(str).str.strip()
    prepared = series.astype("object").where(~is_text, text.map(_rewrite_number))
    blank = series.isna() | (is_text & text.eq(""))
    values = pd.to_numeric(prepared, errors="coerce").mask(blank, 0)
    ambiguous = text.map(lambda value: bool(_AMBIGUOUS_NUMBER.fullmatch(value))).astype(bool)
    return values, ambiguous


def read_quantities(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Numbers where unreadable cells count as 0, with every doubtful cell marked."""
    values, ambiguous = parse_numbers(series)
    return values.fillna(0), values.isna() | ambiguous


def describe_unclear_numbers(column: str, needs_review: pd.Series, what: str = "quantities") -> str | None:
    """Explain flagged numbers with their row numbers in the source file."""
    rows = [int(position) + 2 for position, flagged in enumerate(needs_review.to_numpy()) if flagged]
    if not rows:
        return None
    preview = ", ".join(map(str, rows[:20])) + ("..." if len(rows) > 20 else "")
    return (
        f"{len(rows)} {what} in column '{column}' are unreadable or ambiguous "
        f"(rows {preview}); unreadable ones count as 0. Review the original file."
    )


def sanitize_dataframe(df: pd.DataFrame, text_cols=None) -> pd.DataFrame:
    """
    Cleans leading/trailing whitespaces from all string/object columns across the DataFrame.
    """
    if text_cols is None:
        text_cols = df.select_dtypes(include=['object', 'string']).columns
    for col in text_cols:
        if col in df.columns:
            df[col] = clean_sku_series(df[col])
    return df