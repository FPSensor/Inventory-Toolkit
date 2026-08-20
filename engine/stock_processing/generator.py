import pandas as pd
import numpy as np
import os
from core.logger import log
from core.configuration_manager import ConfigurationManager
from engine.shared.families import build_family_rules, assign_family
from engine.stock_processing.data_processor import process_pricing
from engine.stock_processing.excel_renderer import render_stock_excel

def run_stock_processing(args):
    required_files = [args.stock_processing_raw, args.shared_cost, args.shared_sales]
    for f in required_files:
        if not os.path.exists(f):
            log.error(f"Data file '{f}' not found.")
            return

    log.info(f"Loading configurations for profile: {args.stock_processing_profile}...")
    config = ConfigurationManager(args.stock_processing_profile)

    families_raw = config.get_config('familias')
    family_rules = build_family_rules(families_raw)
    databases_dict = config.get_config('databases')
    settings_dict = config.get_config('settings')
    stores_dict = config.get_config('stores')
    cleaning_dict = config.get_config('cleaning')
    reports_dict = config.get_config('reports')
    
    pricing_dict = config.get_config('pricing') or settings_dict.get('pricing', {})
    
    active_stores = stores_dict.get("locales_activos", [])
    regional_groups = stores_dict.get("grupos_regionales", {})
    
    unnecessary_cols = cleaning_dict.get("columnas_a_eliminar", [])
    text_cols_to_clean = cleaning_dict.get("columnas_texto_a_limpiar", ["Artículo"])
    stock_cols_to_clean = cleaning_dict.get("columnas_a_formatear", [])
    
    base_columns_order = reports_dict.get("orden_columnas_base", ["Artículo", "Familias"])
    raw_data_sheet = reports_dict.get("hoja_datos_crudos", "Datos")
    summaries = reports_dict.get("resumenes", [])

    log.info("Processing Stock data...")
    df_stock = pd.read_excel(args.stock_processing_raw)
    
    col_art_esperada = settings_dict.get('columna_articulo', 'Artículo')
    if col_art_esperada not in df_stock.columns:
        log.error(f"❌ APB Error: Stock file is missing the '{col_art_esperada}' column.")
        print(f"\n❌ APB Error: The file '{os.path.basename(args.stock_processing_raw)}' is NOT a valid Stock file. Missing column '{col_art_esperada}'.")
        return
        
    df_stock = df_stock.drop(columns=[col for col in unnecessary_cols if col in df_stock.columns], errors='ignore')
    
    for col in text_cols_to_clean:
        if col in df_stock.columns:
            df_stock[col] = df_stock[col].astype(str).str.strip()
    
    for col in stock_cols_to_clean:
        if col in df_stock.columns:
            df_stock[col] = df_stock[col].astype(str).str.replace(',', '.', regex=False).str.strip()
            df_stock[col] = pd.to_numeric(df_stock[col], errors='coerce').fillna(0).astype(int)
    
    for local, deposito in databases_dict.items():
        if local in df_stock.columns and deposito in df_stock.columns:
            df_stock[local] = df_stock[local] + df_stock[deposito]
            df_stock = df_stock.drop(columns=[deposito])
            
    for group_name, branches in regional_groups.items():
        df_stock[group_name] = sum(df_stock.get(loc, 0) for loc in branches)
        
    df_stock['Familias'] = df_stock['Artículo'].apply(lambda x: assign_family(x, family_rules))
    
    log.info("Processing pricing files...")
    df_cost = process_pricing(args.shared_cost, pricing_dict)
    df_sales = process_pricing(args.shared_sales, pricing_dict)
    
    if df_cost is not None:
        cost_renames = {col: f"PrecioUnit.Costo.{col}" for col in df_cost.columns if col != 'Artículo'}
        df_cost = df_cost.rename(columns=cost_renames)
        df_stock = pd.merge(df_stock, df_cost, on='Artículo', how='left')
        
    if df_sales is not None:
        sales_renames = {col: f"PrecioUnit.Venta.{col}" for col in df_sales.columns if col != 'Artículo'}
        df_sales = df_sales.rename(columns=sales_renames)
        df_stock = pd.merge(df_stock, df_sales, on='Artículo', how='left')

    price_cols = [c for c in df_stock.columns if c.startswith('PrecioUnit.')]
    df_stock[price_cols] = df_stock[price_cols].fillna(-1).astype(float)
    
    entities_to_value = active_stores + list(regional_groups.keys())
    
    for entity in entities_to_value:
        if entity in regional_groups:
            branches = regional_groups[entity]
            df_stock[f"{entity}.Costo"] = sum(df_stock.get(f"{loc}.Costo", 0) for loc in branches)
            df_stock[f"{entity}.Venta"] = sum(df_stock.get(f"{loc}.Venta", 0) for loc in branches)
        else:
            col_cost = f"PrecioUnit.Costo.{entity}"
            col_sales = f"PrecioUnit.Venta.{entity}"
            if entity in df_stock.columns:
                df_stock[f"{entity}.Costo"] = np.where(df_stock.get(col_cost, 0) <= 0, 0, df_stock[col_cost] * df_stock[entity])
                df_stock[f"{entity}.Venta"] = np.where(df_stock.get(col_sales, 0) <= 0, 0, df_stock[col_sales] * df_stock[entity])

    df_stock = df_stock.drop(columns=price_cols, errors='ignore')
    
    final_col_order = base_columns_order.copy()
    for entity in entities_to_value:
        final_col_order.extend([entity, f"{entity}.Costo", f"{entity}.Venta"])
        
    df_stock = df_stock[[col for col in final_col_order if col in df_stock.columns]]

    final_path = render_stock_excel(args.stock_processing_out, df_stock, summaries, df_stock.columns, raw_data_sheet)
    log.info(f"Process completed. File saved at: {final_path}")
    return final_path
