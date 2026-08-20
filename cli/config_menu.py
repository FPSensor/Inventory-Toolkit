import os
import json
import shutil
from cli.utils import load_json, save_json, clear_screen, ask_file, open_in_editor
from cli.wizard import PANDAS_AVAILABLE

try:
    import pandas as pd
except ImportError:
    pass

PROFILES_DIR = "profiles"

def draw_header(title, profile, filename):
    print("=" * 60)
    print(f" ⚙️  {title.upper()}")
    print(f" Profile: [{profile}] | File: [{filename}]")
    print("=" * 60)

def manage_simple_dictionary(json_path, title, current_profile, parent_key=None):
    root_data = load_json(json_path)
    if root_data is None:
        input("Press Enter to return...")
        return

    data = root_data[parent_key] if parent_key else root_data

    while True:
        clear_screen()
        sub_title = f"{title} > {parent_key}" if parent_key else title
        draw_header(sub_title, current_profile, os.path.basename(json_path))
        
        keys = sorted(data.keys())
        for i, k in enumerate(keys, 1):
            val_type = type(data[k]).__name__
            print(f"  [{i:02d}] {k:<25} = {str(data[k]):<25} ({val_type})")
            
        print("\nActions:")
        print("  [#] Edit Value | [A] Add Key | [D] Delete Key | [0] Back")
        
        cmd = input("\nSelect an option: ").strip()
        
        if cmd == '0':
            break
        elif cmd.upper() == 'A':
            new_k = input("Enter new key name: ").strip()
            if new_k:
                new_v = input(f"Enter value for '{new_k}': ").strip()
                if new_v.lower() in ('true', 'yes', 'y'): new_v = True
                elif new_v.lower() in ('false', 'no', 'n'): new_v = False
                elif new_v.isdigit(): new_v = int(new_v)
                data[new_k] = new_v
                if parent_key:
                    root_data[parent_key] = data
                    save_json(json_path, root_data)
                else:
                    save_json(json_path, data)
        elif cmd.upper() == 'D':
            idx = input("Item number to delete: ").strip()
            if idx.isdigit() and 1 <= int(idx) <= len(keys):
                target = keys[int(idx) - 1]
                del data[target]
                if parent_key:
                    root_data[parent_key] = data
                    save_json(json_path, root_data)
                else:
                    save_json(json_path, data)
        elif cmd.isdigit() and 1 <= int(cmd) <= len(keys):
            target_key = keys[int(cmd) - 1]
            curr_val = data[target_key]
            print(f"\nEditing [{target_key}] (Current: {curr_val})")
            print("  [X] Pick column from Excel file")
            raw_new = input("New value (Leave blank to keep unchanged, or 'X' for Excel): ").strip()
            
            if raw_new.upper() == 'X' and PANDAS_AVAILABLE:
                file_path = ask_file("Path to Excel file to inspect", "")
                if file_path and os.path.exists(file_path):
                    try:
                        df_preview = pd.read_excel(file_path, nrows=0)
                        cols = list(df_preview.columns)
                        print("\nAvailable columns:")
                        for c_idx, c_name in enumerate(cols, 1):
                            print(f"  [{c_idx}] {c_name}")
                        col_choice = input("\nSelect column number: ").strip()
                        if col_choice.isdigit() and 1 <= int(col_choice) <= len(cols):
                            raw_new = cols[int(col_choice) - 1]
                    except Exception as e:
                        print(f"❌ Error: {e}")
                        input("Press Enter...")
                        
            if raw_new and raw_new.upper() != 'X':
                if isinstance(curr_val, bool):
                    data[target_key] = raw_new.lower() in ('true', 'yes', 'y', '1')
                elif isinstance(curr_val, int) and raw_new.isdigit():
                    data[target_key] = int(raw_new)
                else:
                    data[target_key] = raw_new
                if parent_key:
                    root_data[parent_key] = data
                    save_json(json_path, root_data)
                else:
                    save_json(json_path, data)

def manage_list_dictionary(json_path, title, current_profile):
    data = load_json(json_path)
    if data is None:
        input("Press Enter to return...")
        return

    filter_query = ""
    while True:
        clear_screen()
        draw_header(title, current_profile, os.path.basename(json_path))
        
        all_categories = sorted(data.keys())
        categories = [c for c in all_categories if filter_query.lower() in c.lower()] if filter_query else all_categories
        
        if filter_query:
            print(f"🔍 Filter active: '{filter_query}' ({len(categories)} matched)")
            print("  [/] Clear filter")
        
        for i, cat in enumerate(categories, 1):
            val = data[cat]
            if isinstance(val, list):
                meta = f"({len(val)} items) [List]"
            elif isinstance(val, dict):
                meta = f"({len(val)} keys) [Sub-Dictionary]"
            else:
                meta = f"({val}) [{type(val).__name__}]"
            print(f"  [{i:02d}] {cat:<30} {meta}")
            
        print("\nActions:")
        print("  [#] Open Category | [+] New Category | [/] Search/Filter | [D] Delete Category | [0] Back")
        
        cmd = input("\nSelect an action: ").strip()
        
        if cmd == '0':
            break
        elif cmd == '/':
            filter_query = input("Enter search query (or Enter to clear): ").strip()
            continue
        elif cmd == '+':
            new_cat = input("Name of the new category: ").strip()
            if new_cat and new_cat not in data:
                cat_type = input("Category type -> [L] List (default) or [D] Sub-Dictionary? ").strip().upper()
                data[new_cat] = {} if cat_type == 'D' else []
                save_json(json_path, data)
            continue
        elif cmd.upper() == 'D':
            idx = input("Enter the number of the category to delete: ").strip()
            if idx.isdigit() and 1 <= int(idx) <= len(categories):
                target = categories[int(idx) - 1]
                confirm = input(f"Are you sure you want to delete '{target}'? (Y/N): ").strip().upper()
                if confirm == 'Y':
                    del data[target]
                    save_json(json_path, data)
            continue
            
        if not cmd.isdigit() or not (1 <= int(cmd) <= len(categories)):
            continue

        selected_cat = categories[int(cmd) - 1]
        val = data[selected_cat]
        
        if isinstance(val, dict):
            # Llamada limpia sin target_dict fantasma
            manage_simple_dictionary(json_path, title, current_profile, parent_key=selected_cat)
            data = load_json(json_path)
            continue
        elif not isinstance(val, list):
            new_v = input(f"New value for '{selected_cat}' (Current: {val}): ").strip()
            if new_v:
                data[selected_cat] = new_v
                save_json(json_path, data)
            continue

        while True:
            clear_screen()
            draw_header(f"{title} > {selected_cat}", current_profile, os.path.basename(json_path))
            
            items = data[selected_cat]
            if not items:
                print("  (Category is empty)")
            else:
                for idx, itm in enumerate(items, 1):
                    print(f"  [{idx:02d}] {itm}")
                    
            print("\nActions:")
            print("  [A] Add Value(s) | [X] Import from Excel | [E] Edit Item | [D] Delete Item(s) | [0] Back")
            
            action = input("\nAction: ").strip().upper()
            
            if action == '0':
                break
            elif action == 'A':
                raw_input = input("Enter item(s) to add (comma-separated for bulk): ").strip()
                if raw_input:
                    new_entries = [x.strip() for x in raw_input.split(',') if x.strip()]
                    added = 0
                    for entry in new_entries:
                        if entry not in data[selected_cat]:
                            data[selected_cat].append(entry)
                            added += 1
                    save_json(json_path, data)
                    print(f"✅ Added {added} items.")
                    
            elif action == 'X' and PANDAS_AVAILABLE:
                file_path = ask_file("Path to Excel file to inspect", "")
                if file_path and os.path.exists(file_path):
                    try:
                        df_preview = pd.read_excel(file_path, nrows=50)
                        cols = list(df_preview.columns)
                        print("\nAvailable columns in file:")
                        for c_idx, c_name in enumerate(cols, 1):
                            print(f"  [{c_idx}] Column Name: {c_name}")
                        
                        col_choice = input("\nEnter column number to extract values from (or Enter for column names): ").strip()
                        to_add = []
                        if col_choice.isdigit() and 1 <= int(col_choice) <= len(cols):
                            target_col = cols[int(col_choice) - 1]
                            to_add = df_preview[target_col].dropna().astype(str).unique().tolist()
                        else:
                            to_add = cols
                            
                        added = 0
                        for val_it in to_add:
                            val_clean = str(val_it).strip()
                            if val_clean and val_clean not in data[selected_cat]:
                                data[selected_cat].append(val_clean)
                                added += 1
                        save_json(json_path, data)
                        print(f"✅ Extracted and added {added} unique entries.")
                        input("Press Enter to continue...")
                    except Exception as e:
                        print(f"❌ Error inspecting Excel: {e}")
                        input("Press Enter...")
                        
            elif action == 'E' and items:
                idx = input("Item number to edit: ").strip()
                if idx.isdigit() and 1 <= int(idx) <= len(items):
                    old_v = data[selected_cat][int(idx) - 1]
                    new_v = input(f"New value for '{old_v}': ").strip()
                    if new_v:
                        data[selected_cat][int(idx) - 1] = new_v
                        save_json(json_path, data)
                        
            elif action == 'D' and items:
                raw_del = input("Item number(s) to delete (e.g. 1, 3, 5-8): ").strip()
                if raw_del:
                    indices_to_delete = set()
                    for segment in raw_del.split(','):
                        segment = segment.strip()
                        if '-' in segment:
                            parts = segment.split('-')
                            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                                indices_to_delete.update(range(int(parts[0]), int(parts[1]) + 1))
                        elif segment.isdigit():
                            indices_to_delete.add(int(segment))
                    
                    data[selected_cat] = [item for i, item in enumerate(data[selected_cat], 1) if i not in indices_to_delete]
                    save_json(json_path, data)
                    print("🗑️ Selected items deleted.")

def manage_complex_file_with_safety(file_path):
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        input("Press Enter...")
        return
        
    bak_path = file_path + ".bak"
    shutil.copyfile(file_path, bak_path)
    
    while True:
        open_in_editor(file_path)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                json.load(f)
            if os.path.exists(bak_path):
                os.remove(bak_path)
            print("✅ JSON syntax validated successfully.")
            break
        except json.JSONDecodeError as err:
            print("\n" + "!" * 60)
            print(f"❌ JSON SYNTAX ERROR DETECTED:\n{err}")
            print("!" * 60)
            print("[R] Re-open editor to fix | [B] Rollback to previous working version")
            fix_choice = input("Option [R/B]: ").strip().upper()
            if fix_choice == 'B':
                shutil.copyfile(bak_path, file_path)
                if os.path.exists(bak_path):
                    os.remove(bak_path)
                print("🔄 Configuration restored from safety backup.")
                break

def configuration_menu(current_profile):
    config_files = {
        '1': {'file': 'general/familias.json', 'type': 'list', 'title': 'Product Families & Prefixes'},
        '2': {'file': 'stock_processing/cleaning.json', 'type': 'list', 'title': 'Stock Column Cleaning Rules'},
        '3': {'file': 'cross_check/cross_check_settings.json', 'type': 'list', 'title': 'Cross Check Exclusions & Mappings'},
        '4': {'file': 'general/settings.json', 'type': 'simple', 'title': 'General Global Settings'},
        '5': {'file': 'general/databases.json', 'type': 'simple', 'title': 'Database Branch Mappings'},
        '6': {'file': 'yoy_reports/reports.json', 'type': 'complex', 'title': 'YoY Report Structures & Layouts'},
        '7': {'file': 'general/stores.json', 'type': 'complex', 'title': 'Active Stores & Regional Groups'},
        '8': {'file': 'stock_processing/pricing.json', 'type': 'complex', 'title': 'Dynamic Pricing Ingestion Rules'}
    }

    while True:
        clear_screen()
        print("=" * 60)
        print(f"       CONFIGURATION HUB - Active Profile: [{current_profile}]")
        print("=" * 60)
        print("\n📋 BUSINESS RULES & MAPPINGS (Interactive)")
        print("  [1] Product Families & Prefixes (familias.json)")
        print("  [2] Column Cleaning & Normalization (cleaning.json)")
        print("  [3] Cross Check Exclusions & Column Mappings (cross_check_settings.json)")
        
        print("\n🔧 KEY-VALUE SETTINGS (Interactive)")
        print("  [4] General Settings (settings.json)")
        print("  [5] Database Branch Aliases (databases.json)")
        
        print("\n🧠 ADVANCED DATA STRUCTURES (Protected Editor)")
        print("  [6] YoY Report Layouts & Branches (reports.json)")
        print("  [7] Store Networks & Regional Groups (stores.json)")
        print("  [8] Pricing Ingestion Specifications (pricing.json)")
        
        print("\n  [0] ↩️ Return to Main Menu")
        
        opt = input("\nSelect configuration file: ").strip()
        if opt == '0':
            break
            
        if opt in config_files:
            cfg = config_files[opt]
            full_path = os.path.join(PROFILES_DIR, current_profile, "configs", cfg['file'])
            
            if cfg['type'] == 'list':
                manage_list_dictionary(full_path, cfg['title'], current_profile)
            elif cfg['type'] == 'simple':
                manage_simple_dictionary(full_path, cfg['title'], current_profile)
            elif cfg['type'] == 'complex':
                manage_complex_file_with_safety(full_path)
        else:
            print("❌ Invalid option.")
            input("Press Enter to continue...")
