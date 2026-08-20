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

    # 1. Esquema oficial completo para evitar colisiones en ConfigurationManager
    official_schema = {
        "familias": {},
        "databases": {},
        "cleaning": {
            "required": [
                "columnas_a_eliminar",
                "columnas_texto_a_limpiar",
                "columnas_a_formatear"
            ]
        },
        "stores": {
            "required": [
                "locales_activos"
            ]
        },
        "settings": {
            "required": [
                "columna_articulo",
                "columna_familia"
            ]
        }
    }

    templates = {
        "general/schema.json": official_schema,
        "general/familias.json": {
            "REVISAR": ["REVISAR", "revisar"]
        },
        "general/settings.json": {
            "columna_articulo": "Artículo",
            "columna_familia": "Familias",
            "familia_por_defecto": "Otro",
            "calcular_diferencias": True,
            "prefijo_diferencia": "Dif_"
        },
        "general/stores.json": {
            "locales_activos": ["Central"],
            "grupos_regionales": {}
        },
        "general/databases.json": {},
        "stock_processing/cleaning.json": {
            "columnas_texto_a_limpiar": ["Artículo"],
            "columnas_a_eliminar": [],
            "columnas_a_formatear": []
        },
        "stock_processing/pricing.json": {
            "columnas_esperadas": ["Artículo", "Origen - Base de datos", "Precio"],
            "mapeo_nombres": {
                "Origen - Base de datos": "Base"
            }
        },
        "cross_check/cross_check_settings.json": {
            "articulos_ignorados": [],
            "palabras_ignoradas": ["Total general"],
            "columnas_costo": {
                "articulo": "Artículo",
                "precio": "Precio"
            },
            "columnas_venta": {
                "articulo": "Artículo",
                "precio": "Precio"
            }
        },
        "yoy_reports/reports.json": {
            "orden_columnas_base": ["Artículo", "Familias"],
            "hoja_datos_crudos": "Datos",
            "resumenes": [],
            "output_path": "analysis_report.xlsx",
            "data_source": {
                "date_column": "Fecha",
                "quantity_column": "Cantidad",
                "grouping_column": "Familias",
                "item_column": "Articulo",
                "branch_column": "Base"
            },
            "report_structures": {}
        }
    }
    
    for filename, structure in templates.items():
        path = os.path.join(configs_path, filename)
        if not os.path.exists(path):
            save_json(path, structure)

def auto_map_columns(stock_file, profile_dir):
    if not PANDAS_AVAILABLE or not os.path.exists(stock_file):
        return

    print(f"\n--- 🧠 DEEP INSPECTION: {os.path.basename(stock_file)} ---")
    try:
        df_sample = pd.read_excel(stock_file, nrows=20)
        real_columns = list(df_sample.columns)
    except Exception as e:
        print(f"❌ Inspection failed: {e}")
        return

    print("Detected columns in spreadsheet:")
    for i, col in enumerate(real_columns, 1):
        sample_val = str(df_sample[col].dropna().iloc[0]) if not df_sample[col].dropna().empty else "empty"
        print(f"  [{i:02d}] {col:<25} (Sample: {sample_val})")
    print("-" * 60)

    # 1. Article & Family Column Mapping
    mappings = {
        "columna_articulo": {"name": "Article / SKU", "hints": ["artículo", "articulo", "sku", "item", "codigo", "código"]},
        "columna_familia": {"name": "Family / Category", "hints": ["familia", "familias", "rubro", "linea", "categoría", "categoria"]}
    }

    settings_path = os.path.join(profile_dir, "configs", "general", "settings.json")
    settings = load_json(settings_path) or {}

    for cfg_key, meta in mappings.items():
        found = None
        for hint in meta["hints"]:
            matches = [c for c in real_columns if hint in str(c).lower()]
            if matches:
                found = matches[0]
                break
        
        if found:
            print(f"💡 Auto-detected {meta['name']} -> [{found}]")
            if ask_yes_no("Confirm mapping?"):
                settings[cfg_key] = str(found)
                continue
                
        print(f"\nSelect column for '{meta['name']}':")
        for idx, c in enumerate(real_columns, 1):
            print(f"  [{idx}] {c}")
        choice = input("Column number (or 0 to skip): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(real_columns):
            settings[cfg_key] = str(real_columns[int(choice) - 1])

    save_json(settings_path, settings)

    # 2. Store Detection and Setup
    numeric_cols = df_sample.select_dtypes(include='number').columns.tolist()
    excluded = [settings.get("columna_articulo"), settings.get("columna_familia"), "Total", "Precio", "Costo", "Stock"]
    potential_stores = [c for c in numeric_cols if c not in excluded and not any(x in str(c).lower() for x in ['ean', 'id', 'cod', 'barcode'])]
    
    stores_path = os.path.join(profile_dir, "configs", "general", "stores.json")
    stores_data = load_json(stores_path) or {"locales_activos": [], "grupos_regionales": {}}

    if potential_stores:
        print(f"\n🏬 Detected potential store/branch columns: {potential_stores}")
        if ask_yes_no("Auto-populate active stores list with these columns?"):
            stores_data["locales_activos"] = potential_stores
            save_json(stores_path, stores_data)
            print("✅ Stores configuration populated.")
    else:
        print("\n🏬 Manual Store Configuration")
        raw_stores = input("Enter your active store/branch names (comma-separated, e.g. Central, Sucursal1): ").strip()
        if raw_stores:
            stores_list = [s.strip() for s in raw_stores.split(',') if s.strip()]
            stores_data["locales_activos"] = stores_list
            save_json(stores_path, stores_data)
            print(f"✅ Registered stores: {stores_list}")

    print("\n✅ Auto-configuration completed successfully.")
    input("Press Enter to continue...")
