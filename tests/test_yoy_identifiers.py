"""Product and location codes retain their identity during Excel import."""
import pandas as pd
from engine.yoy_reports.data_processor import process_sales_data


def test_numeric_looking_identifiers_keep_leading_zeroes(tmp_path):
    path = tmp_path / "sales.xlsx"
    pd.DataFrame({"Date": ["2026-01-02"], "SKU": ["00012"], "Location": ["01"],
                  "Variant": ["005"], "Category": ["Food"], "Quantity": [1.25]}).to_excel(path, index=False)
    config = {"input": {"date_column": "Date", "item_column": "SKU", "branch_column": "Location",
        "variant_column": "Variant", "grouping_column": "Category", "quantity_column": "Quantity"},
        "output": {"metrics": ["units"], "include_variants": True}}
    current, _, _ = process_sales_data(path, pd.Timestamp("2026-01-01"), pd.Timestamp("2026-01-31"), config)
    assert current.loc[0, ["SKU", "Location", "Variant"]].tolist() == ["00012", "01", "005"]
    assert current["Quantity"].sum() == 1.25
