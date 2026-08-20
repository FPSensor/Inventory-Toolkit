import os
import pandas as pd
from core.logger import log
from core.configuration_manager import ConfigurationManager
from engine.shared.families import build_family_rules, assign_family
from engine.inventory_cross_check.data_processor import normalize_article, calculate_difference
from engine.inventory_cross_check.excel_renderer import apply_excel_formatting
from core.system_utils import safe_pandas_to_excel
from core.system_utils import safe_pandas_to_excel

def run_cross_check(args):
    required_files = [args.cross_check_system, args.cross_check_count, args.shared_cost, args.shared_sales]
    for f in required_files:
        if not os.path.exists(f):
            log.error(f"File not found: '{f}'")
            return

    log.info(f"Loading configuration for profile: {args.cross_check_profile}...")
    config = ConfigurationManager(profile=args.cross_check_profile)

    families_raw = config.get_config('familias')
    family_rules = build_family_rules(families_raw)

    cross_check_cfg = config.get_config('cross_check_settings')
    if not cross_check_cfg:
        cross_check_cfg = {}

    ignored_articles = cross_check_cfg.get('articulos_ignorados', [])
    ignored_words = cross_check_cfg.get('palabras_ignoradas', [])

    cc_cost = cross_check_cfg.get('columnas_costo', {})
    cc_sales = cross_check_cfg.get('columnas_venta', {})

    col_cost_art = cc_cost.get('articulo', 'Artículo') if isinstance(cc_cost, dict) else 'Artículo'
    col_cost_price = cc_cost.get('precio', 'Precio') if isinstance(cc_cost, dict) else 'Precio'
    col_sales_art = cc_sales.get('articulo', 'Artículo') if isinstance(cc_sales, dict) else 'Artículo'
    col_sales_price = cc_sales.get('precio', 'Precio') if isinstance(cc_sales, dict) else 'Precio'

    log.info("Processing files...")
    df_system = pd.read_excel(args.cross_check_system)

    if 'Artículo' not in df_system.columns or 'Cantidad' not in df_system.columns:
        log.error("❌ APB Error: System file is missing 'Artículo' or 'Cantidad'. Wrong file selected?")
        print(f"\n❌ APB Error: The file '{os.path.basename(args.cross_check_system)}' is NOT a valid System file. Missing key columns.")
        return

    df_count = pd.read_excel(args.cross_check_count, header=None, names=['Artículo_Lectura'])
    df_cost = pd.read_excel(args.shared_cost)

    if col_cost_art not in df_cost.columns or col_cost_price not in df_cost.columns:
        log.error(f"❌ APB Error: Cost file missing '{col_cost_art}' or '{col_cost_price}'.")
        print(f"\n❌ APB Error: The file '{os.path.basename(args.shared_cost)}' is NOT a valid Cost file. Missing configured columns.")
        return

    df_sales = pd.read_excel(args.shared_sales)

    if col_sales_art not in df_sales.columns or col_sales_price not in df_sales.columns:
        log.error(f"❌ APB Error: Sales file missing '{col_sales_art}' or '{col_sales_price}'.")
        print(f"\n❌ APB Error: The file '{os.path.basename(args.shared_sales)}' is NOT a valid Sales file. Missing configured columns.")
        return

    df_system['Artículo'] = df_system['Artículo'].astype(str).str.strip()
    df_system['Cantidad'] = pd.to_numeric(df_system['Cantidad'], errors='coerce').fillna(0)
    master_base = df_system['Artículo'].unique().tolist()
    master_set = set([str(x).upper().strip() for x in master_base])

    df_cost.rename(columns={col_cost_art: 'Artículo', col_cost_price: 'Costo'}, inplace=True)
    df_sales.rename(columns={col_sales_art: 'Artículo', col_sales_price: 'Precio'}, inplace=True)
    df_cost['Artículo'] = df_cost['Artículo'].astype(str).str.strip().apply(lambda x: x.split()[0] if x else x)
    df_sales['Artículo'] = df_sales['Artículo'].astype(str).str.strip().apply(lambda x: x.split()[0] if x else x)

    df_count = df_count.dropna(subset=['Artículo_Lectura'])
    df_count['Artículo_Lectura'] = df_count['Artículo_Lectura'].astype(str).str.strip()
    df_count['Total_Original'] = 1

    log.info("Normalizing scanned codes...")
    df_count['Artículo'] = df_count['Artículo_Lectura'].apply(lambda x: normalize_article(x, master_base, master_set))

    if args.cross_check_consolidate:
        df_system_cons = df_system.groupby('Artículo', as_index=False)['Cantidad'].sum()
    else:
        df_system_cons = df_system[['Artículo', 'Cantidad']].copy()

    df_system_cons.rename(columns={'Cantidad': 'Stock Sistema'}, inplace=True)
    df_count_cons = df_count.groupby('Artículo', as_index=False)['Total_Original'].sum()
    df_count_cons.rename(columns={'Total_Original': 'Conteo Físico'}, inplace=True)

    df_cost_cons = df_cost.groupby('Artículo')['Costo'].mean().reset_index()
    df_sales_cons = df_sales.groupby('Artículo')['Precio'].mean().reset_index()

    if args.cross_check_partial:
        df_cross = pd.merge(df_count_cons, df_system_cons, on='Artículo', how='left')
    else:
        df_cross = pd.merge(df_count_cons, df_system_cons, on='Artículo', how='outer')

    df_cross['Conteo Físico'] = df_cross['Conteo Físico'].fillna(0)
    df_cross['Stock Sistema'] = df_cross['Stock Sistema'].fillna(0)

    if ignored_articles:
        df_cross = df_cross[~df_cross['Artículo'].isin(ignored_articles)]
    for word in ignored_words:
        df_cross = df_cross[~df_cross['Artículo'].str.contains(word, case=False, na=False)]

    df_cross['Diferencia'] = df_cross.apply(lambda row: calculate_difference(row['Stock Sistema'], row['Conteo Físico']), axis=1)
    df_cross['Familias'] = df_cross['Artículo'].apply(lambda x: assign_family(x, family_rules))

    df_final = df_cross.merge(df_cost_cons, on='Artículo', how='left')
    df_final = df_final.merge(df_sales_cons, on='Artículo', how='left')

    df_final['CTOTAL'] = df_final['Diferencia'] * df_final['Costo'].fillna(0)
    df_final['VTOTAL'] = df_final['Diferencia'] * df_final['Precio'].fillna(0)

    df_final = df_final[df_final['Diferencia'] != 0].copy()
    cols = ['Familias', 'Artículo', 'Stock Sistema', 'Conteo Físico', 'Diferencia', 'CTOTAL', 'VTOTAL']
    df_final = df_final[cols].sort_values(by=['Familias', 'Artículo'])

    final_path = safe_pandas_to_excel(df_final, args.cross_check_out, index=False)
    final_path = apply_excel_formatting(final_path)
    
    log.info(f"Process completed. File saved at: {final_path}")
    return final_path
