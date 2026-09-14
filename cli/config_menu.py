"""
config_menu.py — Configuration Hub for Inventory Toolkit.

All config files are edited in-app through interactive menus.
No external editor is opened for any file, including reports.json
and pricing.json which previously used manage_complex_file_with_safety.

Menu layout:
  [1] Product families          (familias.json)      — list editor
  [2] Column cleaning rules     (cleaning.json)       — list editor
  [3] Cross Check exclusions    (cross_check_settings.json) — list editor
  [4] General settings          (settings.json)       — key-value editor
  [5] Database aliases          (databases.json)      — key-value editor
  [6] Active stores & groups    (stores.json)         — interactive stores editor
  [7] YoY report structure      (reports.json)        — in-app structured editor
  [8] Pricing rules             (pricing.json)        — in-app structured editor
  [W] Quick Setup Wizard
"""

import os

from cli.utils import load_json, save_json, clear_screen, ask_file, ask_yes_no
from cli.wizard import PANDAS_AVAILABLE, run_setup_wizard

try:
    import pandas as pd
except ImportError:
    pass

PROFILES_DIR = "profiles"


# ── Headers ───────────────────────────────────────────────────────────────────

def _header(title: str, profile: str, filename: str = "") -> None:
    print("=" * 60)
    print(f"  ⚙️  {title.upper()}")
    if filename:
        print(f"  Profile: [{profile}]  |  File: [{filename}]")
    else:
        print(f"  Profile: [{profile}]")
    print("=" * 60)


# ── Simple dictionary editor (key → scalar) ───────────────────────────────────

def manage_simple_dictionary(json_path, title, current_profile, parent_key=None):
    root_data = load_json(json_path)
    if root_data is None:
        input("  Press Enter to return...")
        return

    data = root_data[parent_key] if parent_key else root_data

    while True:
        clear_screen()
        sub = f"{title} > {parent_key}" if parent_key else title
        _header(sub, current_profile, os.path.basename(json_path))

        keys = sorted(data.keys())
        for i, k in enumerate(keys, 1):
            print(f"  [{i:02d}] {k:<28} = {str(data[k])}")

        print("\n  [#] Edit  |  [A] Add key  |  [D] Delete key  |  [0] Back")
        cmd = input("\n  Option: ").strip()

        if cmd == "0":
            break

        elif cmd.upper() == "A":
            k = input("  New key name: ").strip()
            if k:
                v = input(f"  Value for '{k}': ").strip()
                if v.lower() in ("true", "yes", "y"):
                    v = True
                elif v.lower() in ("false", "no", "n"):
                    v = False
                elif v.lstrip("-").isdigit():
                    v = int(v)
                data[k] = v
                _persist(json_path, root_data, data, parent_key)

        elif cmd.upper() == "D":
            idx = input("  Item number to delete: ").strip()
            if idx.isdigit() and 1 <= int(idx) <= len(keys):
                del data[keys[int(idx) - 1]]
                _persist(json_path, root_data, data, parent_key)

        elif cmd.isdigit() and 1 <= int(cmd) <= len(keys):
            target = keys[int(cmd) - 1]
            curr_v = data[target]
            print(f"\n  Editing [{target}]  (Current: {curr_v})")
            if PANDAS_AVAILABLE:
                print("  Type a new value or 'X' to pick a column from an Excel file.")
            raw = input("  New value: ").strip()

            if raw.upper() == "X" and PANDAS_AVAILABLE:
                fp = ask_file("Excel file to inspect", "")
                if fp and os.path.exists(fp):
                    try:
                        cols = list(pd.read_excel(fp, nrows=0).columns)
                        for ci, cn in enumerate(cols, 1):
                            print(f"  [{ci}] {cn}")
                        cc = input("  Column number: ").strip()
                        if cc.isdigit() and 1 <= int(cc) <= len(cols):
                            raw = cols[int(cc) - 1]
                    except Exception as e:
                        print(f"  ❌ Error: {e}")
                        input("  Press Enter...")

            if raw and raw.upper() != "X":
                if isinstance(curr_v, bool):
                    data[target] = raw.lower() in ("true", "yes", "y", "1")
                elif isinstance(curr_v, int) and raw.lstrip("-").isdigit():
                    data[target] = int(raw)
                else:
                    data[target] = raw
                _persist(json_path, root_data, data, parent_key)


def _persist(json_path, root_data, data, parent_key):
    if parent_key:
        root_data[parent_key] = data
        save_json(json_path, root_data)
    else:
        save_json(json_path, data)


# ── List-of-strings dictionary ────────────────────────────────────────────────

def manage_list_dictionary(json_path, title, current_profile):
    data = load_json(json_path)
    if data is None:
        input("  Press Enter to return...")
        return

    filter_q = ""
    while True:
        clear_screen()
        _header(title, current_profile, os.path.basename(json_path))

        all_cats = sorted(data.keys())
        cats = [c for c in all_cats if filter_q.lower() in c.lower()] if filter_q else all_cats

        if filter_q:
            print(f"  🔍 Filter active: '{filter_q}'  ({len(cats)} results)")

        for i, cat in enumerate(cats, 1):
            val = data[cat]
            if isinstance(val, list):
                meta = f"({len(val)} items) [List]"
            elif isinstance(val, dict):
                meta = f"({len(val)} keys) [Sub-Dictionary]"
            else:
                meta = f"({val}) [{type(val).__name__}]"
            print(f"  [{i:02d}] {cat:<32} {meta}")

        print("\n  [#] Open  |  [+] New category  |  [/] Search  |  [D] Delete  |  [0] Back")
        cmd = input("\n  Action: ").strip()

        if cmd == "0":
            break

        elif cmd == "/":
            filter_q = input("  Search text (Enter to clear): ").strip()

        elif cmd == "+":
            new_cat = input("  New category name: ").strip()
            if new_cat and new_cat not in data:
                tipo = input("  Type → [L] List (default) or [D] Sub-Dictionary? ").strip().upper()
                data[new_cat] = {} if tipo == "D" else []
                save_json(json_path, data)

        elif cmd.upper() == "D":
            idx = input("  Number to delete: ").strip()
            if idx.isdigit() and 1 <= int(idx) <= len(cats):
                target = cats[int(idx) - 1]
                if ask_yes_no(f"  Delete '{target}'?"):
                    del data[target]
                    save_json(json_path, data)

        elif cmd.isdigit() and 1 <= int(cmd) <= len(cats):
            selected = cats[int(cmd) - 1]
            val = data[selected]

            if isinstance(val, dict):
                manage_simple_dictionary(json_path, title, current_profile, parent_key=selected)
                data = load_json(json_path)
                continue

            elif not isinstance(val, list):
                new_v = input(f"  New value for '{selected}' (Current: {val}): ").strip()
                if new_v:
                    data[selected] = new_v
                    save_json(json_path, data)
                continue

            # ── List editor ──────────────────────────────────────────────────
            while True:
                clear_screen()
                _header(f"{title} > {selected}", current_profile, os.path.basename(json_path))

                items = data[selected]
                if not items:
                    print("  (Empty category)")
                else:
                    for idx, itm in enumerate(items, 1):
                        print(f"  [{idx:02d}] {itm}")

                print("\n  [A] Add  |  [X] Import from Excel  |  [E] Edit  |  [D] Delete  |  [0] Back")
                action = input("\n  Action: ").strip().upper()

                if action == "0":
                    break

                elif action == "A":
                    raw = input("  Item(s) to add (comma-separated): ").strip()
                    if raw:
                        new_entries = [x.strip() for x in raw.split(",") if x.strip()]
                        added = sum(
                            1 for e in new_entries
                            if e not in data[selected]
                            and not data[selected].append(e)  # noqa: side-effect
                        )
                        save_json(json_path, data)
                        print(f"  ✅ {added} item(s) added.")

                elif action == "X" and PANDAS_AVAILABLE:
                    fp = ask_file("Excel file to inspect", "")
                    if fp and os.path.exists(fp):
                        try:
                            df_prev = pd.read_excel(fp, nrows=50)
                            cols = list(df_prev.columns)
                            print("\n  Available columns:")
                            for ci, cn in enumerate(cols, 1):
                                print(f"    [{ci}] {cn}")
                            cc = input("\n  Column number to extract values (Enter = column names): ").strip()
                            to_add = []
                            if cc.isdigit() and 1 <= int(cc) <= len(cols):
                                to_add = df_prev[cols[int(cc) - 1]].dropna().astype(str).unique().tolist()
                            else:
                                to_add = cols
                            added = 0
                            for v in to_add:
                                vc = str(v).strip()
                                if vc and vc not in data[selected]:
                                    data[selected].append(vc)
                                    added += 1
                            save_json(json_path, data)
                            print(f"  ✅ {added} unique entries imported.")
                            input("  Press Enter...")
                        except Exception as e:
                            print(f"  ❌ Error: {e}")
                            input("  Press Enter...")

                elif action == "E" and items:
                    idx = input("  Number to edit: ").strip()
                    if idx.isdigit() and 1 <= int(idx) <= len(items):
                        old = data[selected][int(idx) - 1]
                        new_v = input(f"  New value for '{old}': ").strip()
                        if new_v:
                            data[selected][int(idx) - 1] = new_v
                            save_json(json_path, data)

                elif action == "D" and items:
                    raw_del = input("  Number(s) to delete (e.g. 1, 3, 5-8): ").strip()
                    if raw_del:
                        indices = set()
                        for seg in raw_del.split(","):
                            seg = seg.strip()
                            if "-" in seg:
                                parts = seg.split("-")
                                if len(parts) == 2 and all(p.isdigit() for p in parts):
                                    indices.update(range(int(parts[0]), int(parts[1]) + 1))
                            elif seg.isdigit():
                                indices.add(int(seg))
                        data[selected] = [
                            itm for i, itm in enumerate(data[selected], 1)
                            if i not in indices
                        ]
                        save_json(json_path, data)
                        print("  🗑️  Items deleted.")


# ── Stores interactive manager ────────────────────────────────────────────────

def manage_stores(json_path: str, title: str, current_profile: str) -> None:
    while True:
        data = load_json(json_path) or {"locales_activos": [], "grupos_regionales": {}}
        clear_screen()
        _header(title, current_profile, os.path.basename(json_path))

        activos = data.get("locales_activos", [])
        grupos  = data.get("grupos_regionales", {})

        print("  📍 ACTIVE STORES")
        if activos:
            for i, loc in enumerate(activos, 1):
                print(f"    [{i:02d}] {loc}")
        else:
            print("    (none)")

        print("\n  🗂️  REGIONAL GROUPS")
        grp_list = sorted(grupos.keys())
        if grp_list:
            for grp in grp_list:
                print(f"    {grp} → {grupos[grp]}")
        else:
            print("    (none)")

        print()
        print("  ─ Stores ─")
        print("  [A] Add store  |  [D] Delete store")
        print("  ─ Groups ─")
        print("  [G] New group  |  [E] Edit group  |  [X] Delete group")
        print("  [0] Back")

        cmd = input("\n  Action: ").strip().upper()

        if cmd == "0":
            break

        elif cmd == "A":
            raw = input("  Store(s) to add (comma-separated): ").strip()
            if raw:
                for loc in [s.strip() for s in raw.split(",") if s.strip()]:
                    if loc not in activos:
                        activos.append(loc)
                data["locales_activos"] = activos
                save_json(json_path, data)

        elif cmd == "D":
            if not activos:
                print("  No stores to delete.")
                input("  Press Enter...")
                continue
            for i, loc in enumerate(activos, 1):
                print(f"    [{i}] {loc}")
            raw_del = input("  Number(s) to delete (e.g. 1,3): ").strip()
            if raw_del:
                to_remove = set()
                for p in raw_del.split(","):
                    p = p.strip()
                    if p.isdigit() and 1 <= int(p) <= len(activos):
                        to_remove.add(activos[int(p) - 1])
                data["locales_activos"] = [l for l in activos if l not in to_remove]
                save_json(json_path, data)

        elif cmd == "G":
            gname = input("  New group name: ").strip()
            if gname and gname not in grupos:
                raw = input(f"  Stores for group '{gname}' (comma-separated): ").strip()
                grupos[gname] = [s.strip() for s in raw.split(",") if s.strip()] if raw else []
                data["grupos_regionales"] = grupos
                save_json(json_path, data)

        elif cmd == "E":
            if not grp_list:
                print("  No groups to edit.")
                input("  Press Enter...")
                continue
            for i, grp in enumerate(grp_list, 1):
                print(f"    [{i}] {grp} → {grupos[grp]}")
            idx = input("  Group number to edit: ").strip()
            if idx.isdigit() and 1 <= int(idx) <= len(grp_list):
                gname = grp_list[int(idx) - 1]
                print(f"  Current stores for '{gname}': {grupos[gname]}")
                raw = input("  New stores (comma-separated): ").strip()
                if raw:
                    grupos[gname] = [s.strip() for s in raw.split(",") if s.strip()]
                    data["grupos_regionales"] = grupos
                    save_json(json_path, data)

        elif cmd == "X":
            if not grp_list:
                print("  No groups to delete.")
                input("  Press Enter...")
                continue
            for i, grp in enumerate(grp_list, 1):
                print(f"    [{i}] {grp}")
            idx = input("  Group number to delete: ").strip()
            if idx.isdigit() and 1 <= int(idx) <= len(grp_list):
                gname = grp_list[int(idx) - 1]
                if ask_yes_no(f"  Delete group '{gname}'?"):
                    del grupos[gname]
                    data["grupos_regionales"] = grupos
                    save_json(json_path, data)

        else:
            print("  ❌ Invalid option.")
            input("  Press Enter...")


# ── In-app reports.json editor ────────────────────────────────────────────────

def manage_yoy_reports(json_path: str, current_profile: str) -> None:
    """
    Structured in-app editor for yoy_reports/reports.json.
    Sections:
      [1] Data source columns   (data_source sub-object)
      [2] Output settings       (output_path, metricas_salida, comparacion_anual, etc.)
      [3] Size settings         (incluir_talles, columna_talle)
      [4] Report summaries      (resumenes list)
      [5] Report structures     (report_structures dict)
    """
    while True:
        data = load_json(json_path) or {}
        clear_screen()
        _header("YoY Report Structure Editor", current_profile, "reports.json")

        ds = data.get("data_source", {})
        print("  [1] Data Source Columns")
        print(f"      date={ds.get('date_column','—')}  qty={ds.get('quantity_column','—')}")
        print(f"      item={ds.get('item_column','—')}  group={ds.get('grouping_column','—')}")
        print(f"      branch={ds.get('branch_column','—')}")
        print()
        print("  [2] Output Settings")
        print(f"      output_path={data.get('output_path','—')}")
        print(f"      metrics={data.get('metricas_salida','—')}")
        print(f"      annual_comparison={data.get('comparacion_anual','—')}")
        print(f"      raw_sheet={data.get('hoja_datos_crudos','—')}")
        print()
        print("  [3] Size Settings")
        print(f"      include_sizes={data.get('incluir_talles','—')}")
        print(f"      size_column={data.get('columna_talle','—')}")
        print()
        print(f"  [4] Report Summaries        ({len(data.get('resumenes', []))} defined)")
        print(f"  [5] Report Structures       ({len(data.get('report_structures', {}))} defined)")
        print()
        print("  [0] Back")

        cmd = input("\n  Option: ").strip()

        if cmd == "0":
            break

        elif cmd == "1":
            # Edit data_source columns
            clear_screen()
            _header("Data Source Columns", current_profile, "reports.json > data_source")
            ds = data.get("data_source", {})
            fields = [
                ("date_column",     "Date column"),
                ("quantity_column", "Quantity column"),
                ("item_column",     "Item / SKU column"),
                ("grouping_column", "Grouping column (Family)"),
                ("branch_column",   "Branch / Store column"),
            ]
            for key, label in fields:
                curr = ds.get(key, "")
                print(f"  {label:<28}  Current: [{curr}]")
                new_v = input(f"    New value (Enter to keep): ").strip()
                if new_v:
                    ds[key] = new_v
            data["data_source"] = ds
            save_json(json_path, data)
            print("  ✅ Data source columns saved.")
            input("  Press Enter...")

        elif cmd == "2":
            # Edit output settings
            clear_screen()
            _header("Output Settings", current_profile, "reports.json")
            fields = [
                ("output_path",         "Output file path"),
                ("hoja_datos_crudos",   "Raw data sheet name"),
                ("comparacion_anual",   "Annual comparison (true/false)"),
            ]
            for key, label in fields:
                curr = data.get(key, "")
                print(f"  {label:<32}  Current: [{curr}]")
                new_v = input(f"    New value (Enter to keep): ").strip()
                if new_v:
                    if key == "comparacion_anual":
                        data[key] = new_v.lower() in ("true", "yes", "y", "1")
                    else:
                        data[key] = new_v

            # Metrics list
            metrics = data.get("metricas_salida", [])
            print(f"\n  Output metrics  Current: {metrics}")
            print("  (common values: unidades, ventas, margen)")
            raw_m = input("  Comma-separated metrics (Enter to keep): ").strip()
            if raw_m:
                data["metricas_salida"] = [x.strip() for x in raw_m.split(",") if x.strip()]

            # Columns order
            orden = data.get("orden_columnas_base", [])
            print(f"\n  Base column order  Current: {orden}")
            raw_o = input("  Comma-separated columns (Enter to keep): ").strip()
            if raw_o:
                data["orden_columnas_base"] = [x.strip() for x in raw_o.split(",") if x.strip()]

            save_json(json_path, data)
            print("  ✅ Output settings saved.")
            input("  Press Enter...")

        elif cmd == "3":
            # Size settings
            clear_screen()
            _header("Size Settings", current_profile, "reports.json")
            curr_include = data.get("incluir_talles", False)
            curr_col     = data.get("columna_talle", "Talle")
            print(f"  Include sizes (incluir_talles)  Current: [{curr_include}]")
            new_v = input("  New value (true/false, Enter to keep): ").strip()
            if new_v:
                data["incluir_talles"] = new_v.lower() in ("true", "yes", "y", "1")
            print(f"  Size column (columna_talle)     Current: [{curr_col}]")
            new_v = input("  New value (Enter to keep): ").strip()
            if new_v:
                data["columna_talle"] = new_v
            save_json(json_path, data)
            print("  ✅ Size settings saved.")
            input("  Press Enter...")

        elif cmd == "4":
            # Resumenes list — show JSON, allow raw edit
            clear_screen()
            _header("Report Summaries (resumenes)", current_profile, "reports.json")
            resumenes = data.get("resumenes", [])
            if resumenes:
                for i, r in enumerate(resumenes, 1):
                    print(f"  [{i}] sheet={r.get('nombre_hoja','?')}  "
                          f"stores={r.get('locales_a_incluir','?')}")
            else:
                print("  (No summaries defined)")

            print("\n  [A] Add summary  |  [D] Delete summary  |  [0] Back")
            sub = input("  Action: ").strip().upper()
            if sub == "A":
                nombre = input("  Sheet name (nombre_hoja): ").strip()
                raw_loc = input("  Stores to include (comma-separated): ").strip()
                locales = [s.strip() for s in raw_loc.split(",") if s.strip()]
                raw_tit = input("  Column titles (comma-separated, optional): ").strip()
                titulos = [s.strip() for s in raw_tit.split(",") if s.strip()] if raw_tit else []
                entry = {"nombre_hoja": nombre, "locales_a_incluir": locales}
                if titulos:
                    entry["titulos"] = titulos
                resumenes.append(entry)
                data["resumenes"] = resumenes
                save_json(json_path, data)
                print(f"  ✅ Summary '{nombre}' added.")
                input("  Press Enter...")
            elif sub == "D" and resumenes:
                idx = input("  Summary number to delete: ").strip()
                if idx.isdigit() and 1 <= int(idx) <= len(resumenes):
                    del resumenes[int(idx) - 1]
                    data["resumenes"] = resumenes
                    save_json(json_path, data)
                    print("  🗑️  Summary deleted.")
                    input("  Press Enter...")

        elif cmd == "5":
            # Report structures dict
            clear_screen()
            _header("Report Structures (report_structures)", current_profile, "reports.json")
            structs = data.get("report_structures", {})
            if structs:
                for k, v in structs.items():
                    print(f"  {k} → {v}")
            else:
                print("  (No structures defined)")

            print("\n  [A] Add  |  [D] Delete  |  [E] Edit  |  [0] Back")
            sub = input("  Action: ").strip().upper()
            if sub == "A":
                key = input("  Group key name: ").strip()
                raw = input("  Store list (comma-separated): ").strip()
                structs[key] = [s.strip() for s in raw.split(",") if s.strip()]
                data["report_structures"] = structs
                save_json(json_path, data)
                print(f"  ✅ Structure '{key}' added.")
                input("  Press Enter...")
            elif sub == "D" and structs:
                keys = sorted(structs.keys())
                for i, k in enumerate(keys, 1):
                    print(f"  [{i}] {k}")
                idx = input("  Number to delete: ").strip()
                if idx.isdigit() and 1 <= int(idx) <= len(keys):
                    del structs[keys[int(idx) - 1]]
                    data["report_structures"] = structs
                    save_json(json_path, data)
                    print("  🗑️  Structure deleted.")
                    input("  Press Enter...")
            elif sub == "E" and structs:
                keys = sorted(structs.keys())
                for i, k in enumerate(keys, 1):
                    print(f"  [{i}] {k} → {structs[k]}")
                idx = input("  Number to edit: ").strip()
                if idx.isdigit() and 1 <= int(idx) <= len(keys):
                    key = keys[int(idx) - 1]
                    raw = input(f"  New stores for '{key}' (comma-separated): ").strip()
                    if raw:
                        structs[key] = [s.strip() for s in raw.split(",") if s.strip()]
                        data["report_structures"] = structs
                        save_json(json_path, data)
                        print(f"  ✅ Structure '{key}' updated.")
                    input("  Press Enter...")


# ── In-app pricing.json editor ────────────────────────────────────────────────

def manage_pricing(json_path: str, current_profile: str) -> None:
    """
    Structured in-app editor for stock_processing/pricing.json.
    Fields:
      columnas_esperadas — list of column names expected in price list files
      mapeo_nombres      — dict of column renames (long name → short alias)
    """
    while True:
        data = load_json(json_path) or {"columnas_esperadas": [], "mapeo_nombres": {}}
        clear_screen()
        _header("Pricing Rules Editor", current_profile, "pricing.json")

        cols_esp = data.get("columnas_esperadas", [])
        mapeo    = data.get("mapeo_nombres", {})

        print("  EXPECTED COLUMNS (columnas_esperadas)")
        if cols_esp:
            for i, c in enumerate(cols_esp, 1):
                print(f"    [{i}] {c}")
        else:
            print("    (none)")

        print("\n  COLUMN ALIASES (mapeo_nombres)")
        if mapeo:
            for original, alias in mapeo.items():
                print(f"    '{original}' → '{alias}'")
        else:
            print("    (none)")

        print()
        print("  ─ Expected columns ─")
        print("  [A] Add column  |  [D] Delete column")
        print("  ─ Aliases ─")
        print("  [M] Add alias   |  [R] Remove alias")
        print("  [0] Back")

        cmd = input("\n  Action: ").strip().upper()

        if cmd == "0":
            break

        elif cmd == "A":
            raw = input("  Column name(s) to add (comma-separated): ").strip()
            if raw:
                for col in [s.strip() for s in raw.split(",") if s.strip()]:
                    if col not in cols_esp:
                        cols_esp.append(col)
                data["columnas_esperadas"] = cols_esp
                save_json(json_path, data)
                print(f"  ✅ Columns added.")

        elif cmd == "D" and cols_esp:
            for i, c in enumerate(cols_esp, 1):
                print(f"  [{i}] {c}")
            raw_del = input("  Number(s) to delete (comma-separated): ").strip()
            if raw_del:
                to_remove = set()
                for p in raw_del.split(","):
                    p = p.strip()
                    if p.isdigit() and 1 <= int(p) <= len(cols_esp):
                        to_remove.add(cols_esp[int(p) - 1])
                data["columnas_esperadas"] = [c for c in cols_esp if c not in to_remove]
                save_json(json_path, data)

        elif cmd == "M":
            original = input("  Original column name: ").strip()
            alias    = input("  Short alias: ").strip()
            if original and alias:
                mapeo[original] = alias
                data["mapeo_nombres"] = mapeo
                save_json(json_path, data)
                print(f"  ✅ Alias added: '{original}' → '{alias}'")

        elif cmd == "R" and mapeo:
            keys = sorted(mapeo.keys())
            for i, k in enumerate(keys, 1):
                print(f"  [{i}] '{k}' → '{mapeo[k]}'")
            idx = input("  Number to remove: ").strip()
            if idx.isdigit() and 1 <= int(idx) <= len(keys):
                del mapeo[keys[int(idx) - 1]]
                data["mapeo_nombres"] = mapeo
                save_json(json_path, data)
                print("  🗑️  Alias removed.")

        else:
            if cmd not in ("0",):
                print("  ❌ Invalid option.")
                input("  Press Enter...")


# ── Main configuration hub ────────────────────────────────────────────────────

def configuration_menu(current_profile: str) -> None:
    while True:
        clear_screen()
        print("=" * 60)
        print(f"       ⚙️  CONFIGURATION — Active profile: [{current_profile}]")
        print("=" * 60)

        print("\n  📋 BUSINESS RULES (interactive editor)")
        print("  [1] Product families           (familias.json)")
        print("  [2] Column cleaning rules      (cleaning.json)")
        print("  [3] Cross Check exclusions     (cross_check_settings.json)")

        print("\n  🔧 GENERAL CONFIGURATION (interactive editor)")
        print("  [4] General settings           (settings.json)")
        print("  [5] Database aliases           (databases.json)")

        print("\n  🏬 STORES & NETWORKS (interactive editor)")
        print("  [6] Active stores & groups     (stores.json)")

        print("\n  🧠 ADVANCED STRUCTURES (in-app editor)")
        print("  [7] YoY report structure       (reports.json)")
        print("  [8] Pricing rules              (pricing.json)")

        print("\n  🚀 SETUP")
        print("  [W] Quick Setup Wizard")

        print("\n  [0] ↩️  Back to main menu")

        opt = input("\n  Select an option: ").strip().upper()

        if opt == "0":
            break

        base = os.path.join(PROFILES_DIR, current_profile, "configs")

        if opt == "1":
            manage_list_dictionary(
                os.path.join(base, "general", "familias.json"),
                "Product Families", current_profile
            )
        elif opt == "2":
            manage_list_dictionary(
                os.path.join(base, "stock_processing", "cleaning.json"),
                "Column Cleaning Rules", current_profile
            )
        elif opt == "3":
            manage_list_dictionary(
                os.path.join(base, "cross_check", "cross_check_settings.json"),
                "Cross Check — Exclusions & Mappings", current_profile
            )
        elif opt == "4":
            manage_simple_dictionary(
                os.path.join(base, "general", "settings.json"),
                "General Settings", current_profile
            )
        elif opt == "5":
            manage_simple_dictionary(
                os.path.join(base, "general", "databases.json"),
                "Database Aliases", current_profile
            )
        elif opt == "6":
            manage_stores(
                os.path.join(base, "general", "stores.json"),
                "Active Stores & Regional Groups", current_profile
            )
        elif opt == "7":
            manage_yoy_reports(
                os.path.join(base, "yoy_reports", "reports.json"),
                current_profile
            )
        elif opt == "8":
            manage_pricing(
                os.path.join(base, "stock_processing", "pricing.json"),
                current_profile
            )
        elif opt == "W":
            profile_path = os.path.join(PROFILES_DIR, current_profile)
            run_setup_wizard(profile_path, current_profile)
        else:
            print("  ❌ Invalid option.")
            input("  Press Enter to continue...")
