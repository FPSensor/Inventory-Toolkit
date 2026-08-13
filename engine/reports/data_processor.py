import pandas as pd

def process_sales_data(file_path, start_dt, end_dt, config):
    col_f = config["data_source"]["date_column"]
    col_c = config["data_source"]["quantity_column"]
    
    df = pd.read_excel(file_path, sheet_name=0)
    if col_f in df.columns:
        df = df[df[col_f] != col_f]
    df[col_f] = pd.to_datetime(df[col_f], errors='coerce')
    df[col_c] = pd.to_numeric(df[col_c], errors='coerce')

    start_prev = start_dt - pd.DateOffset(years=1)
    end_prev = end_dt - pd.DateOffset(years=1)

    df_curr = df[(df[col_f] >= start_dt) & (df[col_f] <= end_dt)].copy()
    df_prev = df[(df[col_f] >= start_prev) & (df[col_f] <= end_prev)].copy()
    
    return df_curr, df_prev, start_prev
