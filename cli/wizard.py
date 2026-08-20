import os
from cli.utils import save_json, load_json, ask_yes_no

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

def initialize_profile_files(configs_path):
    os.makedirs(os.path.join(configs_path, "general"), exist_ok=True)
    os.makedirs(os.path.join(configs_path, "cross_check"), exist_ok=True)
    os.makedirs(os.path.join(configs_path, "stock_processing"), exist_ok=True)
    os.makedirs(os.path.join(configs_path, "yoy_reports"), exist_ok=True)

    templates = {
        "general/familias.json": {},
        "stock_processing/cleaning.json": {"columnas_texto_a_limpiar": [], "columnas_a_eliminar": [], "columnas_a_formatear": []},
        "general/settings.json": {"columna_articulo": "Artículo", "columna_familia": "Familias", "calcular_diferencias": True},
        "general/databases.json": {},
        "yoy_reports/reports.json": {"orden_columnas_base": [], "resumenes": []},
        "general/stores.json": {"locales_activos": [], "grupos_regionales": {}},
        "general/schema.json": {},
        "cross_check/cross_check_settings.json": {"articulos_ignorados": [], "palabras_ignoradas": [], "columnas_costo": {"articulo": "Artículo", "precio": "Precio"}, "columnas_venta": {"articulo": "Artículo", "precio": "Precio"}},
        "stock_processing/pricing.json": {"columnas_esperadas": ["Artículo", "Origen - Base de datos", "Precio"], "mapeo_nombres": {"Origen - Base de datos": "Base"}}
    }
    
    for filename, structure in templates.items():
        path = os.path.join(configs_path, filename)
        if not os.path.exists(path):
            save_json(path, structure)

def auto_map_columns(file_path, profile_dir):
    if not PANDAS_AVAILABLE or not os.path.exists(file_path): return

    print(f"\n--- 🧠 ANALYZING STRUCTURE: {os.path.basename(file_path)} ---")
    try:
        df = pd.read_excel(file_path, nrows=0)
        real_columns = list(df.columns)
    except Exception as e:
        print(f"❌ Could not read file for auto-mapping: {e}")
        return

    print("Detected columns:")
    for i, col in enumerate(real_columns, 1):
        print(f"  [{i}] {col}")
    print("-" * 40)

    mappings_needed = {
        "columna_articulo": {"desc": "Article / Product Code", "candidates": ["Artículo", "Articulo", "Cod", "Codigo", "SKU", "Art"]},
        "columna_familia": {"desc": "Family / Category", "candidates": ["Familia", "Familias", "Rubro", "Categoria", "Línea"]}
    }

    settings_path = os.path.join(profile_dir, "configs", "general", "settings.json")
    current_settings = load_json(settings_path) or {}

    for config_key, map_data in mappings_needed.items():
        suggested_col = None
        for candidate in map_data["candidates"]:
            matches = [c for c in real_columns if candidate.lower() in str(c).lower()]
            if matches:
                suggested_col = matches[0]
                break
        
        if suggested_col:
            print(f"\n💡 We think the column for '{map_data['desc']}' is: [{suggested_col}]")
            is_correct = ask_yes_no("Is this correct?")
            if is_correct:
                current_settings[config_key] = str(suggested_col)
                print(f"✅ Mapping saved: {config_key} = {suggested_col}")
                continue
                
        print(f"\nWhich column represents '{map_data['desc']}'?")
        for i, col in enumerate(real_columns, 1):
            print(f"  [{i}] {col}")
        print("  [0] Skip configuration for now")
        
        while True:
            selection = input("Select the corresponding number: ").strip()
            if selection == '0': break
            elif selection.isdigit() and 1 <= int(selection) <= len(real_columns):
                chosen_col = str(real_columns[int(selection) - 1])
                current_settings[config_key] = chosen_col
                print(f"✅ Manual mapping saved: {config_key} = {chosen_col}")
                break
            else:
                print("❌ Invalid selection.")

    save_json(settings_path, current_settings)
    print("\n✅ File analysis and mapping complete.")
    input("Press Enter to continue...")
