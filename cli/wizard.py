"""
wizard.py — Comprehensive Setup Wizard for Inventory Toolkit.

Covers ALL configuration modules in a single guided flow:
  Step 1  — Load sample Stock Excel
  Step 2  — Article / SKU column               → settings.json
  Step 3  — Family / Category column           → settings.json
  Step 4  — Active store columns               → stores.json + cleaning.json
  Step 5  — Columns to delete                  → cleaning.json
  Step 6  — YoY report columns                 → reports.json (data_source)
  Step 7  — Price list columns                 → pricing.json
  Step 8  — Cross Check columns                → cross_check_settings.json

Any step can be skipped with 'S' — "continue later" from the
Configuration menu.  Progress is saved after every completed step.
"""

import os
from cli.utils import save_json, load_json, ask_yes_no, ask_file

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


# ── Column-detection hints ────────────────────────────────────────────────────

_ARTICLE_HINTS  = ["artículo", "articulo", "sku", "item", "codigo", "código"]
_FAMILY_HINTS   = ["familia", "familias", "rubro", "linea", "categoría", "categoria"]
_DATE_HINTS     = ["fecha", "date", "fec"]
_QTY_HINTS      = ["cantidad", "qty", "quantity", "cant"]
_BRANCH_HINTS   = ["base", "sucursal", "local", "branch", "tienda", "store"]
_PRICE_HINTS    = ["precio", "price", "costo", "cost"]
_DB_HINTS       = ["origen", "base de datos", "database", "db"]
_NON_STORE_SKIP = ["ean", "id", "cod", "barcode", "precio", "costo", "stock",
                   "total", "fecha", "date", "cantidad", "qty"]


# ── Default file structure ────────────────────────────────────────────────────

def initialize_profile_files(configs_path: str) -> None:
    """
    Create the default config JSON files for a brand-new profile.
    Only writes files that do not already exist.
    """
    os.makedirs(os.path.join(configs_path, "general"),          exist_ok=True)
    os.makedirs(os.path.join(configs_path, "cross_check"),      exist_ok=True)
    os.makedirs(os.path.join(configs_path, "stock_processing"), exist_ok=True)
    os.makedirs(os.path.join(configs_path, "yoy_reports"),      exist_ok=True)

    defaults = {
        "general/familias.json": {
            "REVISAR": ["REVISAR", "revisar"]
        },
        "general/settings.json": {
            "columna_articulo":    "Artículo",
            "columna_familia":     "Familias",
            "familia_por_defecto": "Otro",
            "calcular_diferencias": True,
            "prefijo_diferencia":   "Dif_"
        },
        "general/stores.json": {
            "locales_activos":   [],
            "grupos_regionales": {}
        },
        "general/databases.json": {},
        "stock_processing/cleaning.json": {
            "columnas_texto_a_limpiar": ["Artículo"],
            "columnas_a_eliminar":      [],
            "columnas_a_formatear":     []
        },
        "stock_processing/pricing.json": {
            "columnas_esperadas": ["Artículo", "Origen - Base de datos", "Precio"],
            "mapeo_nombres":      {"Origen - Base de datos": "Base"}
        },
        "cross_check/cross_check_settings.json": {
            "articulos_ignorados": [],
            "palabras_ignoradas":  ["Total general"],
            "columnas_costo":      {"articulo": "Artículo", "precio": "Precio"},
            "columnas_venta":      {"articulo": "Artículo", "precio": "Precio"}
        },
        "yoy_reports/reports.json": {
            "metricas_salida":      ["unidades", "ventas"],
            "comparacion_anual":    True,
            "incluir_talles":       False,
            "columna_talle":        "Talle",
            "orden_columnas_base":  ["Artículo", "Familias"],
            "hoja_datos_crudos":    "Datos",
            "resumenes":            [],
            "output_path":          "analysis_report.xlsx",
            "data_source": {
                "date_column":     "Fecha",
                "quantity_column": "Cantidad",
                "grouping_column": "Familias",
                "item_column":     "Articulo",
                "branch_column":   "Base"
            },
            "report_structures": {}
        }
    }

    for rel_path, content in defaults.items():
        full_path = os.path.join(configs_path, rel_path)
        if not os.path.exists(full_path):
            save_json(full_path, content)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _auto_detect(columns: list, hints: list):
    """Return the first column whose name contains any hint (case-insensitive)."""
    for hint in hints:
        for col in columns:
            if hint in str(col).lower():
                return col
    return None


def _pick_column(label: str, columns: list, hints: list, current: str = None,
                 allow_skip: bool = True) -> str | None:
    """
    Try to auto-detect a column from *hints*.
    If found → ask for confirmation.
    Otherwise → show numbered menu.
    Returns chosen column name, or None if the user skips.
    """
    suggestion = _auto_detect(columns, hints)

    if suggestion:
        print(f"  💡 Auto-detected for '{label}': [{suggestion}]")
        if ask_yes_no("     Confirm?"):
            return suggestion

    print(f"\n  Select the column for '{label}':")
    for i, col in enumerate(columns, 1):
        print(f"    [{i:02d}] {col}")
    if current:
        print(f"    [ 0] Keep current value: '{current}'")
    if allow_skip:
        print(f"    [ S] Skip this step (configure later)")

    while True:
        choice = input("  Number: ").strip().upper()
        if choice == "S" and allow_skip:
            return None
        if choice == "0" and current:
            return current
        if choice.isdigit() and 1 <= int(choice) <= len(columns):
            return columns[int(choice) - 1]
        print("  ❌ Invalid number.")


def _section_header(title: str, step: int, total: int) -> None:
    print(f"\n  {'─' * 56}")
    print(f"  Step {step}/{total}: {title}")
    print(f"  {'─' * 56}")
    print(f"  (Enter 'S' at any column prompt to skip this step)")


def _skip_notice() -> None:
    print("  ⏭️  Step skipped — you can configure this from the Configuration menu later.")


# ── Public API ────────────────────────────────────────────────────────────────

def run_setup_wizard(profile_dir: str, profile_name: str = "") -> None:
    """
    Comprehensive interactive wizard to configure ALL modules from a sample Excel.

    Writes:
      • general/settings.json          — article column, family column
      • general/stores.json            — active stores
      • stock_processing/cleaning.json — columns to format / delete / clean
      • stock_processing/pricing.json  — price list column mapping
      • cross_check/cross_check_settings.json — cost/sales list column mapping
      • yoy_reports/reports.json       — data_source column mapping
    """
    if not PANDAS_AVAILABLE:
        print("  ⚠️  Pandas is not installed. Configure the JSON files manually.")
        input("  Press Enter to continue...")
        return

    TOTAL_STEPS = 8

    print("\n" + "=" * 60)
    print(f"  🧙  SETUP WIZARD  —  {profile_name or profile_dir}")
    print("=" * 60)
    print("  This wizard reads your Stock or Sales file and configures")
    print("  every module automatically. Any step can be skipped")
    print("  and completed later from the Configuration menu.\n")

    # ── Step 1: Load sample Excel ─────────────────────────────────────────────
    _section_header("Load sample Stock or Sales Excel file", 1, TOTAL_STEPS)
    stock_file = ask_file("Sample file (Stock or Sales data)", "")
    if not stock_file or not os.path.exists(stock_file):
        print("\n  ⚠️  No file loaded. You can run the wizard later from:")
        print("       Main menu → ⚙️  Configuration → [W] Quick Setup Wizard")
        input("  Press Enter to continue...")
        return

    try:
        df = pd.read_excel(stock_file, nrows=50)
        columns = list(df.columns)
    except Exception as e:
        print(f"\n  ❌ Could not read the file: {e}")
        input("  Press Enter to continue...")
        return

    print(f"\n  📋 {len(columns)} columns detected:")
    for i, col in enumerate(columns, 1):
        vals = df[col].dropna()
        sample = str(vals.iloc[0])[:22] if not vals.empty else "—"
        print(f"    [{i:02d}] {col:<34}  (e.g. {sample})")

    configs_path  = os.path.join(profile_dir, "configs")
    settings_path = os.path.join(configs_path, "general",          "settings.json")
    stores_path   = os.path.join(configs_path, "general",          "stores.json")
    cleaning_path = os.path.join(configs_path, "stock_processing", "cleaning.json")
    pricing_path  = os.path.join(configs_path, "stock_processing", "pricing.json")
    cc_path       = os.path.join(configs_path, "cross_check",      "cross_check_settings.json")
    reports_path  = os.path.join(configs_path, "yoy_reports",      "reports.json")

    settings = load_json(settings_path) or {}
    stores   = load_json(stores_path)   or {"locales_activos": [], "grupos_regionales": {}}
    cleaning = load_json(cleaning_path) or {
        "columnas_texto_a_limpiar": [],
        "columnas_a_eliminar":      [],
        "columnas_a_formatear":     []
    }
    pricing  = load_json(pricing_path)  or {
        "columnas_esperadas": ["Artículo", "Origen - Base de datos", "Precio"],
        "mapeo_nombres":      {}
    }
    cc       = load_json(cc_path)       or {
        "articulos_ignorados": [],
        "palabras_ignoradas":  ["Total general"],
        "columnas_costo":      {"articulo": "Artículo", "precio": "Precio"},
        "columnas_venta":      {"articulo": "Artículo", "precio": "Precio"}
    }
    reports  = load_json(reports_path)  or {
        "data_source": {
            "date_column":     "Fecha",
            "quantity_column": "Cantidad",
            "grouping_column": "Familias",
            "item_column":     "Articulo",
            "branch_column":   "Base"
        }
    }

    col_art = settings.get("columna_articulo")
    col_fam = settings.get("columna_familia")
    active_stores: list = stores.get("locales_activos", [])

    # ── Step 2: Article column ────────────────────────────────────────────────
    _section_header("Article / SKU column", 2, TOTAL_STEPS)
    chosen = _pick_column("Article / SKU", columns, _ARTICLE_HINTS, col_art)
    if chosen is None:
        _skip_notice()
    else:
        col_art = chosen
        settings["columna_articulo"] = col_art
        save_json(settings_path, settings)
        print(f"  ✅ Article column set to: '{col_art}'")

    # ── Step 3: Family column ─────────────────────────────────────────────────
    _section_header("Family / Category column", 3, TOTAL_STEPS)
    chosen = _pick_column("Family / Category", columns, _FAMILY_HINTS, col_fam)
    if chosen is None:
        _skip_notice()
    else:
        col_fam = chosen
        settings["columna_familia"] = col_fam
        save_json(settings_path, settings)
        print(f"  ✅ Family column set to: '{col_fam}'")

    # ── Step 4: Active stores ─────────────────────────────────────────────────
    _section_header("Active store columns (branch columns)", 4, TOTAL_STEPS)
    numeric_cols    = df.select_dtypes(include="number").columns.tolist()
    excluded_always = {col_art, col_fam, "Total", "Precio", "Costo", "Stock"}
    candidate_stores = [
        c for c in numeric_cols
        if c not in excluded_always
        and not any(x in str(c).lower() for x in _NON_STORE_SKIP)
    ]

    skip_stores = False
    if candidate_stores:
        print(f"  🏬 Possible store columns detected: {candidate_stores}")
        resp = input("  [Y] Use these as active stores  [N] Enter manually  [S] Skip: ").strip().upper()
        if resp == "S":
            _skip_notice()
            skip_stores = True
        elif resp == "Y":
            active_stores = candidate_stores
        else:
            raw = input("  Enter store names separated by commas: ").strip()
            if raw:
                active_stores = [s.strip() for s in raw.split(",") if s.strip()]
    else:
        print("  No store columns detected automatically.")
        resp = input("  Enter store names manually (comma-separated) or 'S' to skip: ").strip().upper()
        if resp == "S":
            _skip_notice()
            skip_stores = True
        elif resp:
            active_stores = [s.strip() for s in resp.split(",") if s.strip()]

    if not skip_stores:
        stores["locales_activos"] = active_stores
        cleaning["columnas_a_formatear"] = active_stores
        save_json(stores_path, stores)
        save_json(cleaning_path, cleaning)
        print(f"  ✅ Active stores: {active_stores}")

    # ── Step 5: Columns to delete ─────────────────────────────────────────────
    _section_header("Columns to delete from processed output", 5, TOTAL_STEPS)
    core_keep = set(filter(None, [col_art, col_fam] + active_stores))
    other_cols = [c for c in columns if c not in core_keep]
    if not other_cols:
        print("  No additional columns to review.")
    else:
        print("  Columns that are not article, family, or store:")
        for i, col in enumerate(other_cols, 1):
            print(f"    [{i:02d}] {col}")
        print("  Enter the numbers of columns to DELETE, or 'S' to skip.")
        raw_del = input("  Numbers (e.g. 1,3,5) or 'S': ").strip().upper()
        if raw_del == "S":
            _skip_notice()
        elif raw_del:
            to_del = []
            for part in raw_del.split(","):
                p = part.strip()
                if p.isdigit():
                    idx = int(p) - 1
                    if 0 <= idx < len(other_cols):
                        to_del.append(other_cols[idx])
            cleaning["columnas_a_eliminar"] = to_del
            if col_art and col_art not in cleaning.get("columnas_texto_a_limpiar", []):
                cleaning["columnas_texto_a_limpiar"] = [col_art] if col_art else []
            save_json(cleaning_path, cleaning)
            print(f"  ✅ Columns to delete: {to_del}")

    # ── Step 6: YoY report columns ────────────────────────────────────────────
    _section_header("YoY Sales Report — data source columns", 6, TOTAL_STEPS)
    print("  These columns are read from the Sales history file (not Stock).")
    print("  If you do not have a Sales file here, press 'S' to skip.")

    ds = reports.get("data_source", {})
    skip_yoy = False

    date_col = _pick_column("Date column",     columns, _DATE_HINTS,   ds.get("date_column"))
    if date_col is None:
        _skip_notice()
        skip_yoy = True
    else:
        qty_col  = _pick_column("Quantity column", columns, _QTY_HINTS,    ds.get("quantity_column"))
        if qty_col is None:
            _skip_notice()
            skip_yoy = True
        else:
            item_col2 = _pick_column("Item / SKU column", columns, _ARTICLE_HINTS, ds.get("item_column"))
            if item_col2 is None:
                _skip_notice()
                skip_yoy = True
            else:
                grp_col  = _pick_column("Grouping column (Family)", columns, _FAMILY_HINTS, ds.get("grouping_column"))
                if grp_col is None:
                    _skip_notice()
                    skip_yoy = True
                else:
                    branch_col = _pick_column("Branch / Store column", columns, _BRANCH_HINTS, ds.get("branch_column"))
                    if branch_col is None:
                        _skip_notice()
                        skip_yoy = True

    if not skip_yoy:
        reports["data_source"] = {
            "date_column":     date_col,
            "quantity_column": qty_col,
            "grouping_column": grp_col,
            "item_column":     item_col2,
            "branch_column":   branch_col,
        }
        save_json(reports_path, reports)
        print(f"  ✅ YoY data source configured.")

    # ── Step 7: Price list columns (pricing.json) ─────────────────────────────
    _section_header("Price list columns (pricing.json)", 7, TOTAL_STEPS)
    print("  These columns are read from the Cost/Sales price list files.")
    print("  If you do not have a price list here, press 'S' to skip.")

    skip_pricing = False
    p_art = _pick_column("Article column in price list", columns, _ARTICLE_HINTS,
                         pricing.get("columnas_esperadas", ["Artículo"])[0] if pricing.get("columnas_esperadas") else None)
    if p_art is None:
        _skip_notice()
        skip_pricing = True
    else:
        p_price = _pick_column("Price column", columns, _PRICE_HINTS,
                               pricing.get("columnas_esperadas", [None, None, None])[2] if len(pricing.get("columnas_esperadas", [])) > 2 else None)
        if p_price is None:
            _skip_notice()
            skip_pricing = True
        else:
            p_db = _pick_column("Database / Origin column", columns, _DB_HINTS,
                                pricing.get("columnas_esperadas", [None, None])[1] if len(pricing.get("columnas_esperadas", [])) > 1 else None)
            if p_db is None:
                _skip_notice()
                skip_pricing = True

    if not skip_pricing:
        pricing["columnas_esperadas"] = [p_art, p_db, p_price]
        # Auto-add a short alias for the database column
        if p_db and p_db != "Base":
            existing_mapeo = pricing.get("mapeo_nombres", {})
            existing_mapeo.setdefault(p_db, "Base")
            pricing["mapeo_nombres"] = existing_mapeo
        save_json(pricing_path, pricing)
        print(f"  ✅ Price list columns: article={p_art}, database={p_db}, price={p_price}")

    # ── Step 8: Cross Check columns ───────────────────────────────────────────
    _section_header("Cross Check — cost/sales list column mapping", 8, TOTAL_STEPS)
    print("  Map the article and price columns for Cost and Sales price lists.")

    skip_cc = False

    print("\n  — Cost price list —")
    cc_cost_art = _pick_column("Article column (cost list)", columns, _ARTICLE_HINTS,
                               cc.get("columnas_costo", {}).get("articulo"))
    if cc_cost_art is None:
        _skip_notice()
        skip_cc = True
    else:
        cc_cost_price = _pick_column("Price column (cost list)", columns, _PRICE_HINTS,
                                     cc.get("columnas_costo", {}).get("precio"))
        if cc_cost_price is None:
            _skip_notice()
            skip_cc = True
        else:
            print("\n  — Sales price list —")
            cc_sales_art = _pick_column("Article column (sales list)", columns, _ARTICLE_HINTS,
                                        cc.get("columnas_venta", {}).get("articulo"))
            if cc_sales_art is None:
                _skip_notice()
                skip_cc = True
            else:
                cc_sales_price = _pick_column("Price column (sales list)", columns, _PRICE_HINTS,
                                              cc.get("columnas_venta", {}).get("precio"))
                if cc_sales_price is None:
                    _skip_notice()
                    skip_cc = True

    if not skip_cc:
        cc["columnas_costo"] = {"articulo": cc_cost_art,  "precio": cc_cost_price}
        cc["columnas_venta"] = {"articulo": cc_sales_art, "precio": cc_sales_price}
        save_json(cc_path, cc)
        print(f"  ✅ Cross Check columns configured.")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  🏁  SETUP WIZARD COMPLETE")
    print("=" * 60)
    cfg = load_json(settings_path) or {}
    st  = load_json(stores_path)   or {}
    print(f"  Article column   → {cfg.get('columna_articulo', '(not set)')}")
    print(f"  Family column    → {cfg.get('columna_familia',  '(not set)')}")
    print(f"  Active stores    → {st.get('locales_activos', [])}")
    print()
    print("  Any skipped steps can be configured from:")
    print("  Main menu → ⚙️  Configuration")
    print()
    input("  Press Enter to continue...")


# ── Back-compat alias ─────────────────────────────────────────────────────────
def auto_map_columns(stock_file: str, profile_dir: str) -> None:
    run_setup_wizard(profile_dir)
