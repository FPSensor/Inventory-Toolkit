import os
from cli.utils import load_json, save_json, clear_screen, ask_file, open_in_editor
from cli.wizard import PANDAS_AVAILABLE

try:
    import pandas as pd
except ImportError:
    pass

PROFILES_DIR = "profiles"

def manage_list_dictionary(json_path, title, current_profile):
    data = load_json(json_path)
    if data is None:
        input("Press Enter to return...")
        return

    while True:
        clear_screen()
        print(f"--- 🛠️ CONFIGURATION: {title} ---")
        print(f"Profile: {current_profile} | File: {os.path.basename(json_path)}\n")
        
        categories = sorted(data.keys())
        for i, cat in enumerate(categories, 1):
            print(f"[{i}] {cat}")
        print("[0] Return to previous menu")
        print("[+] Create new category")
        
        cat_opt = input("\nSelect an option: ").strip()
        
        if cat_opt == '0': break
        elif cat_opt == '+':
            new_cat = input("Name of the new category: ").strip()
            if new_cat:
                data[new_cat] = []
                save_json(json_path, data)
            continue
            
        if not cat_opt.isdigit() or not (1 <= int(cat_opt) <= len(categories)):
            print("❌ Invalid option.")
            input("Press Enter to try again...")
            continue

        current_category = categories[int(cat_opt) - 1]
        
        while True:
            clear_screen()
            print(f"--- Editing: {current_category.upper()} ---")
            
            items = data[current_category]
            if not isinstance(items, list):
                print("⚠️ This category does not contain an editable list. Returning...")
                input("Press Enter...")
                break

            if not items:
                print("  (Empty list)")
            else:
                for i, item in enumerate(items, 1):
                    print(f"  {i}. {item}")
            
            print("\nActions:")
            print("[A] Add manual entry")
            
            is_col_category = "columna" in current_category.lower() or "column" in current_category.lower()
            if PANDAS_AVAILABLE and is_col_category:
                print("[X] 📊 Extract from an Excel file")
                
            if items:
                print("[C] Correct an item")
                print("[E] Delete an item")
            print("[V] Return to categories")
            
            action = input("\nChoose an action: ").strip().upper()
            
            if action == 'V': break
            elif action == 'A':
                new_item = input("Enter the new value: ").strip()
                if new_item:
                    data[current_category].append(new_item)
                    save_json(json_path, data)
                    
            elif action == 'X' and PANDAS_AVAILABLE and is_col_category:
                print("\n🔍 Looking for file to extract columns...")
                path = ask_file("Path to Excel file", "")
                
                if path and os.path.exists(path):
                    try:
                        df_temp = pd.read_excel(path, nrows=0)
                        cols = list(df_temp.columns)
                        
                        print(f"\n--- Columns in {os.path.basename(path)} ---")
                        for i_col, col_name in enumerate(cols, 1):
                            mark = " ✓ (Already in list)" if col_name in data[current_category] else ""
                            print(f"  [{i_col}] {col_name}{mark}")
                            
                        print("\n💡 You can enter multiple numbers separated by commas (e.g. 1,3,4)")
                        print("  [0] Cancel")
                        selection = input("Select columns to add: ").strip()
                        
                        if selection != '0':
                            added = 0
                            for num_str in selection.split(','):
                                if num_str.strip().isdigit():
                                    idx = int(num_str.strip())
                                    if 1 <= idx <= len(cols):
                                        chosen_col = cols[idx - 1]
                                        if chosen_col not in data[current_category]:
                                            data[current_category].append(chosen_col)
                                            added += 1
                            
                            if added > 0:
                                print(f"✅ Successfully added {added} columns.")
                                save_json(json_path, data)
                            else:
                                print("⚠️ No columns added (already in list or invalid selection).")
                            input("Press Enter to continue...")
                            
                    except Exception as e:
                        print(f"❌ Error reading file: {e}")
                        input("Press Enter...")
                else:
                    print("⚠️ File not found or cancelled.")
                    input("Press Enter...")
                    
            elif action == 'E' and items:
                idx = input("Enter the NUMBER of the item to delete: ").strip()
                if idx.isdigit() and 1 <= int(idx) <= len(items):
                    deleted_item = data[current_category].pop(int(idx) - 1)
                    print(f"🗑️ Deleted: '{deleted_item}'")
                    save_json(json_path, data)
                    input("Press Enter...")
            elif action == 'C' and items:
                idx = input("Enter the NUMBER of the item to correct: ").strip()
                if idx.isdigit() and 1 <= int(idx) <= len(items):
                    old_value = data[current_category][int(idx) - 1]
                    new_value = input(f"New value for '{old_value}': ").strip()
                    if new_value:
                        data[current_category][int(idx) - 1] = new_value
                        save_json(json_path, data)

def manage_simple_dictionary(json_path, title, current_profile):
    data = load_json(json_path)
    if data is None:
        input("Press Enter to return...")
        return

    while True:
        clear_screen()
        print(f"--- 🛠️ CONFIGURATION: {title} ---")
        print(f"Profile: {current_profile} | File: {os.path.basename(json_path)}\n")
        
        keys = sorted(data.keys())
        for i, k in enumerate(keys, 1):
            print(f"[{i}] {k}: {data[k]}")
        
        print("\nActions:")
        print("  [#] Number to edit an existing value")
        print("  [A] Add new key-value pair")
        print("  [E] Delete a key")
        print("  [0] Return to previous menu")
        
        option = input("\nChoose an action: ").strip().upper()
        
        if option == '0': break
        elif option == 'A':
            new_key = input("Enter the name of the new key: ").strip()
            if new_key:
                new_value = input(f"Enter the value for '{new_key}': ").strip()
                if new_value.lower() in ('true', 'si', 's', '1', 'yes', 'y'): new_value = True
                elif new_value.lower() in ('false', 'no', 'n', '0'): new_value = False
                elif new_value.isdigit(): new_value = int(new_value)
                data[new_key] = new_value
                save_json(json_path, data)
        elif option == 'E':
            idx = input("Number of the item to delete: ").strip()
            if idx.isdigit() and 1 <= int(idx) <= len(keys):
                key_to_delete = keys[int(idx) - 1]
                del data[key_to_delete]
                print(f"🗑️ Deleted: {key_to_delete}")
                save_json(json_path, data)
                input("Press Enter...")
        elif option.isdigit() and 1 <= int(option) <= len(keys):
            current_key = keys[int(option) - 1]
            current_value = data[current_key]
            print(f"\nEditing [{current_key}]. Current value: {current_value}")
            new_value = input("Enter the new value (leave blank to cancel): ").strip()
            
            if new_value:
                if isinstance(current_value, bool):
                    data[current_key] = new_value.lower() in ('true', '1', 'si', 's', 'yes', 'y')
                elif isinstance(current_value, int) and new_value.isdigit():
                    data[current_key] = int(new_value)
                else:
                    data[current_key] = new_value
                save_json(json_path, data)

def configuration_menu(current_profile):
    config_files = {
        '1': {'file': 'general/familias.json', 'type': 'list', 'title': 'Product Families'},
        '2': {'file': 'stock_processing/cleaning.json', 'type': 'list', 'title': 'Cleaning Rules'},
        '3': {'file': 'cross_check/cross_check_settings.json', 'type': 'list', 'title': 'Cross Check Exclusions & Settings'},
        '4': {'file': 'general/settings.json', 'type': 'simple', 'title': 'General Settings'},
        '5': {'file': 'general/databases.json', 'type': 'simple', 'title': 'Database Mapping'},
        '6': {'file': 'yoy_reports/reports.json', 'type': 'complex', 'title': 'Report Structures'},
        '7': {'file': 'general/stores.json', 'type': 'complex', 'title': 'Stores & Regions'},
        '8': {'file': 'general/schema.json', 'type': 'complex', 'title': 'Validation Schema'},
        '9': {'file': 'stock_processing/pricing.json', 'type': 'complex', 'title': 'Pricing Settings'}
    }

    while True:
        clear_screen()
        print(f"--- ⚙️ CONFIGURATION CENTER (Profile: {current_profile}) ---")
        print("\n📝 DATA LISTS (Interactive)")
        print("  [1] Product Families")
        print("  [2] Column Cleaning Rules")
        print("  [3] Cross Check Exclusions")
        
        print("\n🔧 BASIC SETTINGS (Interactive)")
        print("  [4] General Settings")
        print("  [5] Database Mappings")
        
        print("\n🧠 COMPLEX STRUCTURES (Opens in external editor)")
        print("  [6] Report Structures")
        print("  [7] Stores and Regions")
        print("  [8] Validation Schema")
        print("  [9] Pricing Settings")
        
        print("\n  [0] ↩️ Return to main menu")
        
        option = input("\nChoose a file to configure: ").strip()
        
        if option == '0': break
            
        if option in config_files:
            selected_config = config_files[option]
            configs_path = os.path.join(PROFILES_DIR, current_profile, "configs")
            file_path = os.path.join(configs_path, selected_config['file'])
            
            if selected_config['type'] == 'list':
                manage_list_dictionary(file_path, selected_config['title'], current_profile)
            elif selected_config['type'] == 'simple':
                manage_simple_dictionary(file_path, selected_config['title'], current_profile)
            elif selected_config['type'] == 'complex':
                open_in_editor(file_path)
        else:
            print("❌ Invalid option.")
            input("Press Enter to continue...")
