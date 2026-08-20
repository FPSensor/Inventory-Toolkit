import pandas as pd
import numpy as np
import os
from core.logger import log

def process_pricing(file_path, pricing_dict=None):
    if not file_path or not os.path.exists(file_path):
        return None
    try:
        df = pd.read_excel(file_path)
        col_article = next((c for c in ['Artículo', 'Articulo', 'SKU', 'Codigo', 'Item'] if c in df.columns), None)
        if not col_article:
            log.warning(f"Article column not found in {file_path}.")
            return None
        df['Artículo'] = df[col_article].astype(str).str.split(' ').str[0]
        
        expected_base_col = None
        if pricing_dict and "mapeo_nombres" in pricing_dict:
            keys_dict = list(pricing_dict["mapeo_nombres"].keys())
            expected_base_col = next((c for c in keys_dict if c in df.columns), None)

        if expected_base_col:
            col_base = expected_base_col
        else:
            base_options = ['Origen - Base de datos', 'Sucursal', 'Base', 'Local', 'Origen', 'Tienda']
            col_base = next((c for c in base_options if c in df.columns), None)
            
        if not col_base:
            col_base = 'Base_General'
            df[col_base] = 'General'
            
        col_value = next((c for c in ['Precio', 'Costo', 'Venta', 'Valor', 'Monto'] if c in df.columns), None)
        if not col_value:
            num_cols = df.select_dtypes(include='number').columns.tolist()
            avail_cols = [c for c in num_cols if c not in [col_article, col_base, 'Talle', 'Color']]
            avail_cols = [c for c in avail_cols if str(c).upper() not in ['EAN', 'ID', 'COD', 'CÓDIGO', 'CODIGO', 'BARCODE']]
            if avail_cols:
                col_value = avail_cols[-1]
            else:
                log.warning(f"Value column not found in {file_path}.")
                return None

        df_pivot = pd.pivot_table(df, index='Artículo', columns=col_base, values=col_value, aggfunc='mean').reset_index()
        df_pivot.columns.name = None
        return df_pivot
    except Exception as e:
        log.error(f"Processing {file_path}: {e}")
        return None

def calculate_margin(df, col_sales, col_cost):
    return np.where(df[col_sales] > 0, (df[col_sales] - df[col_cost]) / df[col_sales], 0)
