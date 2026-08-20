from argparse import Namespace
from cli.utils import clear_screen, ask_file, validate_files_exist
from core.logger import log

def launch_stock_processing(active_profile):
    clear_screen()
    print(f"--- 📦 STARTING STOCK PROCESSING (Profile: {active_profile}) ---\n")
    
    stock_file = ask_file("1. Raw Stock File", "stock_processing_raw_stock.xlsx")
    cost_file = ask_file("2. Cost List File", "shared_cost_list.xlsx")
    sales_file = ask_file("3. Sales Price List File", "shared_sales_price_list.xlsx")
    
    if not validate_files_exist([stock_file, cost_file, sales_file]):
        print("\n⚠️ Operation aborted. Missing required files.")
        input("Press Enter to return to menu...")
        return

    out_file = ask_file("\n4. Output file name", "Stock_Final_Report.xlsx", is_output=True)
    if not out_file.endswith(('.xlsx', '.xls')):
        out_file += ".xlsx"

    print(f"\n🚀 Processing inventory... (Output: {out_file})")
    
    args = Namespace(
        stock_processing_raw=stock_file, 
        shared_cost=cost_file, 
        shared_sales=sales_file, 
        stock_processing_out=out_file, 
        stock_processing_profile=active_profile
    )
    
    try:
        import time
        from engine.stock_processing.generator import run_stock_processing
        start_time = time.time()
        final_out = run_stock_processing(args)
        if final_out:
            elapsed = time.time() - start_time
            print(f"\n✅ Success: Stock Processing generated in {elapsed:.2f} seconds and saved to {final_out}")
    except ImportError as e:
        log.error(f"Cannot execute: Missing modules in 'engine/' ({e}).")
    except Exception as e:
        log.error(f"Critical error: {e}")
        
    input("\nPress Enter to return to menu...")
