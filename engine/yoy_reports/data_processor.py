import pandas as pd
from engine.shared.families import assign_family

def process_sales_data(yoy_file_path, yoy_start_dt, yoy_end_dt, yoy_config, family_rules=None):
    col_f = yoy_config["data_source"]["date_column"]
    col_c = yoy_config["data_source"]["quantity_column"]
    
    df = pd.read_excel(yoy_file_path, sheet_name=0)
    
    # Limpieza básica
    if col_f in df.columns:
        df = df[df[col_f] != col_f]
    df[col_f] = pd.to_datetime(df[col_f], errors='coerce')
    df[col_c] = pd.to_numeric(df[col_c], errors='coerce')

    # Generación dinámica de familias si se requiere
    if family_rules is not None:
        item_col = yoy_config["data_source"]["item_column"]
        fam_col = yoy_config["data_source"]["grouping_column"]
        # Aplica la regla importada de shared/families.py
        df[fam_col] = df[item_col].apply(lambda x: assign_family(x, family_rules))

    yoy_start_prev = yoy_start_dt - pd.DateOffset(years=1)
    end_prev = yoy_end_dt - pd.DateOffset(years=1)

    yoy_df_curr = df[(df[col_f] >= yoy_start_dt) & (df[col_f] <= yoy_end_dt)].copy()
    yoy_df_prev = df[(df[col_f] >= yoy_start_prev) & (df[col_f] <= end_prev)].copy()
    
    return yoy_df_curr, yoy_df_prev, yoy_start_prev
