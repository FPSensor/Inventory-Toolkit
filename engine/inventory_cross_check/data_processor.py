"""Pure data rules for inventory reconciliation."""

import pandas as pd
import numpy as np

from core.business_schema import REVIEW_PREFIX
from core.config.profile_config import DEFAULTS
from core.files.data_sanitizer import describe_unclear_numbers, parse_numbers
from core.files.table_reader import read_table

SCAN_READING_COLUMN = "__scan_reading"
SCAN_COUNT_COLUMN = "__scan_count"
STORE_COLUMN = "__store"


def read_physical_counts(path, settings, overrides=None, on_notice=None):
    """Read scanner lines or an explicitly mapped counted-quantity table."""
    if settings.get("count_mode", "scans") == "scans":
        frame = read_table(path, header=False, on_notice=on_notice).dropna(axis=1, how="all")
        if frame.shape[1] > 1:
            raise ValueError(
                f"The physical count must have one column with one scanner reading per row; "
                f"it has {frame.shape[1]} columns with data. Configure it as a quantity table instead.")
        if frame.empty:
            raise ValueError("The physical count has no scanner readings.")
        frame = frame.set_axis([SCAN_READING_COLUMN], axis=1)
        frame[SCAN_COUNT_COLUMN] = 1
        return frame
    columns = overrides or {"article": settings["count_article_column"], "quantity": settings["count_quantity_column"]}
    article, quantity = columns["article"], columns["quantity"]
    if not article or not quantity or article == quantity:
        raise ValueError("Choose distinct product and quantity columns for the physical count table.")
    frame = read_table(path, text=[article], on_notice=on_notice)
    missing = [column for column in (article, quantity) if column not in frame.columns]
    if missing:
        raise ValueError(f"Physical count is missing configured columns: {missing}")
    result = frame[[article, quantity]].copy()
    result.columns = [SCAN_READING_COLUMN, SCAN_COUNT_COLUMN]
    result[SCAN_COUNT_COLUMN], ambiguous = parse_numbers(result[SCAN_COUNT_COLUMN])
    invalid = ~np.isfinite(result[SCAN_COUNT_COLUMN]) | result[SCAN_COUNT_COLUMN].lt(0)
    unidentified = result[SCAN_READING_COLUMN].isna() | result[SCAN_READING_COLUMN].str.strip().eq("")
    invalid |= unidentified & result[SCAN_COUNT_COLUMN].ne(0)
    if invalid.any():
        rows = [int(position) + 2 for position in np.flatnonzero(invalid.to_numpy())[:20]]
        raise ValueError(f"Physical count has missing products or invalid quantities at Excel rows {rows}.")
    if on_notice:
        on_notice(describe_unclear_numbers(quantity, ambiguous))
    return result



def build_article_index(articles):
    """Return the known article keys and their distinct lengths, longest first."""
    known = {str(article).strip().upper() for article in articles if not pd.isna(article)}
    # Every string starts with "", so an empty article would absorb any reading.
    known.discard("")
    return known, sorted({len(article) for article in known}, reverse=True)


def normalize_article(reading, article_index):
    """Resolve a raw scanner reading to the longest known article.

    Scanner payloads may concatenate an article code, size, color, or other
    suffixes without a reliable delimiter. Article codes are also variable in
    length, so fixed-position slicing would either truncate long codes or leak
    variant data into short ones.

    Known articles are therefore the source of truth: an exact match wins and
    otherwise the longest known prefix does. The result is the uppercase
    article key. Unknown readings are preserved verbatim behind the review
    marker instead of being guessed or discarded.
    """
    if pd.isna(reading):
        return None
    known, lengths = article_index
    code = str(reading).strip().upper()
    for length in lengths:
        if length <= len(code) and code[:length] in known:
            return code[:length]
    return f"{REVIEW_PREFIX}{reading}"


def calculate_difference(
    stock: float,
    count: float,
    *,
    ignore_negative_system_stock_when_counted: bool = DEFAULTS["cross_check/settings"][
        "reconciliation"
    ]["ignore_negative_system_stock_when_counted"],
) -> float:
    """Calculate count minus stock with the caller-selected negative-stock policy."""
    if ignore_negative_system_stock_when_counted and stock < 0 and count > 0:
        return float(count)
    return float(count - stock)
