import pandas as pd
import pytest

from engine.inventory_cross_check.data_processor import read_physical_counts, SCAN_READING_COLUMN, SCAN_COUNT_COLUMN


def test_headered_count_preserves_identifiers_and_fractional_quantities(tmp_path):
    path = tmp_path / "count.xlsx"
    pd.DataFrame({"Product": ["001", "001"], "Weight": [1.25, 0.5]}).to_excel(path, index=False)
    settings = {"count_mode": "quantities", "count_article_column": "Product", "count_quantity_column": "Weight"}
    frame = read_physical_counts(path, settings)
    assert frame[SCAN_READING_COLUMN].tolist() == ["001", "001"]
    assert frame[SCAN_COUNT_COLUMN].sum() == 1.75
    pd.DataFrame({"Product": [None], "Weight": [2]}).to_excel(path, index=False)
    with pytest.raises(ValueError, match=r"Excel rows \[2\]"):
        read_physical_counts(path, settings)
    pd.DataFrame({"Product": ["A"], "Weight": [-1]}).to_excel(path, index=False)
    with pytest.raises(ValueError, match="invalid quantities"):
        read_physical_counts(path, settings)


def test_headerless_scans_still_count_each_row(tmp_path):
    path = tmp_path / "scanner.xlsx"
    pd.DataFrame(["001", "001", "002"]).to_excel(path, index=False, header=False)
    frame = read_physical_counts(path, {"count_mode": "scans"})
    assert frame[SCAN_READING_COLUMN].tolist() == ["001", "001", "002"]
    assert frame[SCAN_COUNT_COLUMN].sum() == 3
