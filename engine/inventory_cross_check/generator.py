import os
import gc
import pandas as pd
from core.logger import log
from core.configuration_manager import ConfigurationManager
from core.system_utils import safe_pandas_to_excel
from core.data_sanitizer import clean_sku_series
from core.telemetry import execution_timer
from engine.shared.families import build_family_rules, vectorize_assign_families
from engine.inventory_cross_check.data_processor import normalize_article, calculate_difference
from engine.inventory_cross_check.excel_renderer import apply_excel_formatting

def run_cross_check(args):
    interactive = not getattr(args, 'non_interactive', False)
    required_files = [args.cross_check_system, args.cross_check_count, args.shared_cost, args.shared_sales]
    for f in required_files:
        if not os.path.exists(f):
            log.error(f"File not found: '{f}'")
            return None

    config = ConfigurationManager(profile=args.cross_check_profile)
    families_raw = config.get_familias()
    family_rules = build_family_rules(families_raw)
    cross_check_cfg = config.get_cross_check_settings()

    ignored_articles = cross_check_cfg.get('articulos_ignorados', [])
    ignored_words = cross_check_cfg.get('palabras_ignoradas', [])
    cc_cost = cross_check_cfg.get('columnas_costo', {})
    cc_sales = cross_check_cfg.get('columnas_venta', {})

    col_cost_art = cc_cost.get('articulo', 'Artículo')
    col_cost_price = cc_cost.get('precio', 'Precio')
    col_sales_art = cc_sales.get('articulo', 'Artículo')
    col_sales_price = cc_sales.get('precio', 'Precio')

    with execution_timer("Read and Validate Spreadsheets"):
        df_system = pd.read_excel(args.cross_check_system)
        if 'Artículo' not in df_system.columns or 'Cantidad' not in df_system.columns:
            log.error("Missing 'Artículo' or 'Cantidad' in system stock.")
            return None

        df_count = pd.read_excel(args.cross_check_count, header=None, names=['Artículo_Lectura'])
        df_cost = pd.read_excel(args.shared_cost)
        df_sales = pd.read_excel(args.shared_sales)

    with execution_timer("Data Transformation & Matching"):
        df_system['Artículo'] = clean_sku_series(df_system['Artículo'])
        df_system['Cantidad'] = pd.to_numeric(df_system['Cantidad'], errors='coerce').fillna(0)
        master_base = df_system['Artículo'].unique().tolist()
        master_set = set([str(x).upper().strip() for x in master_base])

        df_cost.rename(columns={col_cost_art: 'Artículo', col_cost_price: 'Costo'}, inplace=True)
        df_sales.rename(columns={col_sales_art: 'Artículo', col_sales_price: 'Precio'}, inplace=True)
        df_cost['Artículo'] = clean_sku_series(df_cost['Artículo']).apply(lambda x: x.split()[0] if x else x)
        df_sales['Artículo'] = clean_sku_series(df_sales['Artículo']).apply(lambda x: x.split()[0] if x else x)

        df_count = df_count.dropna(subset=['Artículo_Lectura']).copy()
        df_count['Artículo_Lectura'] = clean_sku_series(df_count['Artículo_Lectura'])
        df_count['Total_Original'] = 1

        df_count['Artículo'] = df_count['Artículo_Lectura'].apply(lambda x: normalize_article(x, master_base, master_set))

        if args.cross_check_consolidate:
            df_system_cons = df_system.groupby('Artículo', as_index=False)['Cantidad'].sum()
        else:
            df_system_cons = df_system[['Artículo', 'Cantidad']].copy()

        df_system_cons.rename(columns={'Cantidad': 'Stock Sistema'}, inplace=True)
        df_count_cons = df_count.groupby('Artículo', as_index=False)['Total_Original'].sum().rename(columns={'Total_Original': 'Conteo Físico'})

        df_cost_cons = df_cost.groupby('Artículo', as_index=False)['Costo'].mean()
        df_sales_cons = df_sales.groupby('Artículo', as_index=False)['Precio'].mean()

        how_merge = 'left' if args.cross_check_partial else 'outer'
        df_cross = pd.merge(df_count_cons, df_system_cons, on='Artículo', how=how_merge).fillna(0)

        if ignored_articles:
            df_cross = df_cross[~df_cross['Artículo'].isin(ignored_articles)]
        for word in ignored_words:
            df_cross = df_cross[~df_cross['Artículo'].astype(str).str.contains(word, case=False, na=False)]

        df_cross['Diferencia'] = [calculate_difference(s, c) for s, c in zip(df_cross['Stock Sistema'], df_cross['Conteo Físico'])]
        df_cross['Familias'] = vectorize_assign_families(df_cross['Artículo'], family_rules)

        df_final = df_cross.merge(df_cost_cons, on='Artículo', how='left').merge(df_sales_cons, on='Artículo', how='left')
        df_final['CTOTAL'] = df_final['Diferencia'] * df_final['Costo'].fillna(0)
        df_final['VTOTAL'] = df_final['Diferencia'] * df_final['Precio'].fillna(0)

        df_final = df_final[df_final['Diferencia'] != 0].copy()
        cols = ['Familias', 'Artículo', 'Stock Sistema', 'Conteo Físico', 'Diferencia', 'CTOTAL', 'VTOTAL']
        df_final = df_final[cols].sort_values(by=['Familias', 'Artículo'])

    with execution_timer("Excel Rendering & Formatting"):
        final_path = safe_pandas_to_excel(
            df_final, args.cross_check_out, index=False, interactive=interactive
        )
        apply_excel_formatting(final_path, interactive=interactive)

    # Garbage collection optimization
    del df_system, df_count, df_cost, df_sales, df_cross, df_final
    gc.collect()

    log.info(f"Reconciliation completed successfully: {final_path}")
    return final_path
