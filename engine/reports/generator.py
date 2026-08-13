from engine.reports.data_processor import process_sales_data
from engine.reports.excel_renderer import render_yoy_sales_excel

def generate_sales_report(file_path, output_path, start_dt, end_dt, config, grouping_col, segmented):
    df_curr, df_prev, start_prev = process_sales_data(file_path, start_dt, end_dt, config)
    render_yoy_sales_excel(output_path, df_curr, df_prev, start_dt, end_dt, start_prev, config, grouping_col, segmented)
