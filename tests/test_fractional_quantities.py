from types import SimpleNamespace
import pandas as pd
from openpyxl import load_workbook

from engine.stock_processing.data_processor import prepare_stock_frame
from engine.stock_processing.excel_renderer import render_stock_excel
from engine.yoy_reports.metrics import resolve_metric_specs


def test_store_cleaning_and_excel_preserve_fractional_quantities(tmp_path):
    plan = SimpleNamespace(article_column="SKU", drop_columns=(), text_columns=(),
        numeric_columns=(), active_stores=("Counter",), stock_database_columns={})
    frame = prepare_stock_frame(pd.DataFrame({"SKU": ["A"], "Counter": ["1,25"]}), plan)
    assert frame["Counter"].sum() == 1.25
    export = pd.DataFrame({"SKU": ["A"], "Category": ["Food"], "Counter": [1.25]})
    path = tmp_path / "stock.xlsx"
    render_stock_excel(path, export, [{"sheet_name": "Summary", "entities": ["Counter"]}],
        export.columns, "Stock", family_column="Category", interactive=False,
        quantity_format="#,##0.###", quantity_columns=("Counter",))
    workbook = load_workbook(path)
    assert workbook["Stock"]["C2"].value == 1.25
    assert workbook["Stock"]["C2"].number_format == "#,##0.###"
    assert workbook["Summary"]["B2"].value == 1.25
    assert workbook["Summary"]["B2"].number_format == "#,##0.###"
    workbook.close()
    metric = resolve_metric_specs({"input": {"quantity_column": "Weight"}, "output": {
        "metrics": ["units"], "quantity_label": "Quantity (kg)", "quantity_format": "#,##0.###"}})[0]
    assert metric.label == "Quantity (kg)" and metric.number_format == "#,##0.###"
