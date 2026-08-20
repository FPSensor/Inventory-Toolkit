import os
import sys
from cli.utils import clear_screen, load_json, ask_file, save_json, ask_yes_no
from cli.wizard import initialize_profile_files, auto_map_columns

PROFILES_DIR = "profiles"

def select_profile(current_profile, is_startup=False):
    while True:
        clear_screen()
        print("--- 👤 PROFILE SELECTION ---")
        if current_profile:
            print(f"Current profile: [{current_profile}]\n")
        else:
            print("👋 Welcome! Select or create a profile to begin.\n")
        
        os.makedirs(PROFILES_DIR, exist_ok=True)
        profile_folders = [d for d in os.listdir(PROFILES_DIR) if os.path.isdir(os.path.join(PROFILES_DIR, d))]
        
        if not profile_folders:
            print("⚠️ No profiles found. Please create a new one.")
            
        print("Available profiles:")
        for i, folder in enumerate(profile_folders, 1):
            info_path = os.path.join(PROFILES_DIR, folder, "profile.json")
            display_name, desc_text = folder, ""
            
            if os.path.exists(info_path):
                info = load_json(info_path)
                if info:
                    display_name = info.get("name", folder)
                    desc = info.get("description", "")
                    desc_text = f" - {desc}" if desc else ""
            
            marker = " 🟢 (Active)" if folder == current_profile else ""
            print(f"  [{i}] {display_name}{desc_text}{marker} (Dir: {folder})")
            
        print("\nActions:")
        print("  [N] Create new profile")
        if not is_startup or current_profile:
            print("  [0] Return to main menu")
        elif is_startup and not profile_folders:
            print("  [E] Exit program")
            
        option = input("\nChoose an option: ").strip().upper()
        
        if option == '0' and (not is_startup or current_profile):
            return current_profile
        elif option == 'E' and is_startup and not profile_folders:
            sys.exit(0)
        elif option == 'N':
            new_dir = input("Enter folder name for new profile (e.g. my_company): ").strip().lower().replace(" ", "_")
            if new_dir:
                new_path = os.path.join(PROFILES_DIR, new_dir)
                configs_path = os.path.join(new_path, "configs")
                os.makedirs(configs_path, exist_ok=True)
                
                print("\n--- 🛠️ SETUP WIZARD ---")
                profile_name = input("Profile display name: ").strip() or new_dir
                profile_desc = input("Profile description: ").strip() or "New profile"
                
                print("\n(Optional) Providing sample files speeds up auto-configuration.")
                stock_file = ask_file("Path to sample Stock file", "")
                system_file = ask_file("Path to sample System file (Cross Check)", "")
                
                save_json(os.path.join(new_path, "profile.json"), {
                    "name": profile_name,
                    "description": profile_desc,
                    "version": "1.3.1",
                    "sample_files": {
                        "stock": stock_file,
                        "system": system_file
                    }
                })
                
                initialize_profile_files(configs_path)
                current_profile = new_dir
                print(f"\n✅ Profile '{profile_name}' successfully created.")
                
                if stock_file and os.path.exists(stock_file):
                    if ask_yes_no("Do you want to analyze the Stock file to auto-configure columns?"):
                        auto_map_columns(stock_file, new_path)
                
                if ask_yes_no("Do you want to configure the remaining parameters manually now?"):
                    from cli.config_menu import configuration_menu
                    configuration_menu(current_profile)
                
                if is_startup: return current_profile
        elif option.isdigit() and 1 <= int(option) <= len(profile_folders):
            current_profile = profile_folders[int(option) - 1]
            print(f"✅ Profile successfully changed to '{current_profile}'.")
            input("Press Enter to continue...")
            if is_startup: return current_profile
        else:
            print("❌ Invalid option.")
            input("Press Enter to continue...")
