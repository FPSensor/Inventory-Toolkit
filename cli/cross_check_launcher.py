from argparse import Namespace
from cli.utils import clear_screen, ask_file, validate_files_exist
from core.logger import log

def launch_cross_check(active_profile):
    clear_screen()
    print(f"--- 🔄 STARTING INVENTORY CROSS CHECK (Profile: {active_profile}) ---\n")
    
    system_file = ask_file("1. System Stock File", "cross_check_system_stock.xls")
    count_file = ask_file("2. Physical Count File", "cross_check_physical_count.xlsx")
    cost_file = ask_file("3. Cost List File", "shared_cost_list.xlsx")
    sales_file = ask_file("4. Sales Price List File", "shared_sales_price_list.xlsx")
    
    if not validate_files_exist([system_file, count_file, cost_file, sales_file]):
        print("\n⚠️ Operation aborted. Missing required files.")
        input("Press Enter to return to menu...")
        return

    out_file = ask_file("\n5. Output file name", "Cross_Check_Results.xlsx", is_output=True)
    if not out_file.endswith(('.xlsx', '.xls')):
        out_file += ".xlsx"

    print("\n--- ⚙️ Cross Check Options ---")
    resp_ds = input("Consolidate quantities from multiple databases? (Y/N) [N]: ").strip().upper()
    flag_consolidate = True if resp_ds == 'Y' else False

    resp_partial = input("Filter stock only by scanned articles (Partial Check)? (Y/N) [N]: ").strip().upper()
    flag_partial = True if resp_partial == 'Y' else False

    print(f"\n🚀 Crossing data... (Output: {out_file})")
    
    args = Namespace(
        cross_check_system=system_file,
        cross_check_count=count_file, 
        shared_cost=cost_file, 
        shared_sales=sales_file, 
        cross_check_out=out_file, 
        cross_check_profile=active_profile,
        cross_check_consolidate=flag_consolidate,
        cross_check_partial=flag_partial
    )
    
    try:
        import time
        from engine.inventory_cross_check.generator import run_cross_check
        start_time = time.time()
        final_out = run_cross_check(args)
        if final_out:
            elapsed = time.time() - start_time
            print(f"\n✅ Success: Cross Check generated in {elapsed:.2f} seconds and saved to {final_out}")
    except ImportError as e:
        log.error(f"Cannot execute: Missing modules ({e}).")
    except Exception as e:
        log.error(f"Critical error: {e}")
        
    input("\nPress Enter to return to menu...")
