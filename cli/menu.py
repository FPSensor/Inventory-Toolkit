import sys
import argparse
from cli.utils import clear_screen
from cli.profiles import select_profile
from cli.config_menu import configuration_menu
from cli.cross_check_launcher import launch_cross_check
from cli.stock_processing_launcher import launch_stock_processing
from cli.yoy_reports_launcher import launch_yoy_reports
from cli.wizard import PANDAS_AVAILABLE

try:
    from engine import stock_processing
    from engine import inventory_cross_check
    MODULES_LOADED = True
except ImportError as e:
    MODULES_LOADED = False
    error_msg = e

def main():
    # Hidden arguments for debugging
    parser = argparse.ArgumentParser(description="Inventory Toolkit CLI")
    parser.add_argument('-debug_level', type=int, choices=[1, 2, 3], default=1, help=argparse.SUPPRESS)
    args, unknown = parser.parse_known_args()

    if not PANDAS_AVAILABLE:
        print("⚠️ Warning: Pandas is not installed.")
    
    if not MODULES_LOADED:
        print(f"⚠️ Warning: Could not load base modules ({error_msg}).")
        input("Press Enter to start menu in degraded mode...")

    from core.logger import setup_logger
    log = setup_logger(args.debug_level)
    
    if args.debug_level > 1:
        log.info(f"Starting Inventory Toolkit (Hidden Debug Level: {args.debug_level})...")

    current_profile = select_profile(None, is_startup=True)
    
    try:
        while True:
            clear_screen()
            print("========================================")
            print("       INVENTORY TOOLKIT v1.3.1 CLI       ")
            print(f"       Active Profile: [{current_profile}]  ")
            print("========================================")
            print("What do you want to do today?\n")
            print("  [C] 🔄 Inventory Cross Check")
            print("  [S] 📦 Stock Processing")
            print("  [R] 📊 YoY Sales Report")
            print("  [K] ⚙️ Configurations (JSON)")
            print("  [P] 👤 Change Profile")
            print("  [E] 🚪 Exit")
            print("========================================")
            
            option = input("Choose an option: ").strip().upper()
            
            if option == 'C': launch_cross_check(current_profile)
            elif option == 'S': launch_stock_processing(current_profile)
            elif option == 'K': configuration_menu(current_profile)
            elif option == 'R': launch_yoy_reports(current_profile)
            elif option == 'P': current_profile = select_profile(current_profile)
            elif option == 'E': sys.exit(0)
            
    except KeyboardInterrupt:
        print("\n\n⚠️ Operation aborted. Exiting safely...")
        sys.exit(0)
