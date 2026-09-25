"""Pure data rules for inventory reconciliation."""

import pandas as pd

from core.business_schema import REVIEW_PREFIX


def normalize_article(reading, master_articles, master_set):
    """Resolve a raw scanner reading to the longest valid system article.

    Scanner payloads may concatenate an article code, size, color, or other
    suffixes without a reliable delimiter. Article codes are also variable in
    length, so fixed-position slicing would either truncate long codes or leak
    variant data into short ones.

    The system stock therefore acts as the source of truth: exact matches win
    immediately; otherwise every known article that prefixes the reading is a
    candidate and the longest candidate wins. Unknown readings are preserved
    verbatim behind the business-facing review marker instead of being guessed
    or discarded.
    """
    if pd.isna(reading):
        return None

    normalized_reading = str(reading).upper().strip()
    if normalized_reading and normalized_reading in master_set:
        return normalized_reading

    # Empty master articles are invalid prefix candidates: every string starts
    # with "", so allowing one here would silently normalize an unknown scanner
    # reading to an empty article instead of preserving it for manual review.
    matches = [
        article
        for article in master_articles
        if not pd.isna(article)
        and str(article).strip()
        and normalized_reading.startswith(str(article).upper().strip())
    ]
    if not matches:
        return f"{REVIEW_PREFIX}{reading}"

    matches.sort(key=len, reverse=True)
    return matches[0]


def calculate_difference(stock: float, count: float) -> float:
    """Return the business-defined physical-vs-system inventory difference."""
    if stock < 0 and count > 0:
        return float(count)
    return float(count - stock)
