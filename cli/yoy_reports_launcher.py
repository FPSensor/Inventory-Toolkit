import os
import pandas as pd
import tkinter as tk
from tkinter import filedialog
from core.configuration_manager import ConfigurationManager
from engine.yoy_reports.generator import generate_sales_report
from core.logger import log

def launch_yoy_reports(active_profile):
    print("\n--- Year-over-Year Sales Report Generation ---")
    yoy_profile = active_profile if active_profile else 'demo'
    
    cm = ConfigurationManager(profile=yoy_profile)
    yoy_config = cm.get_reports()
    
    if not yoy_config or "data_source" not in yoy_config:
        log.error(f"No valid report configuration found for profile '{yoy_profile}'.")
        input("Press Enter to return...")
        return
            
    yoy_file_path = input("Enter sales file path (or press 'B' to browse): ").strip()
    
    if yoy_file_path.lower() == 'b':
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        yoy_file_path = filedialog.askopenfilename(title="Select File", filetypes=[("Excel Files", "*.xlsx *.xls")])
        root.destroy()
        if not yoy_file_path: return
            
    while True:
        group_opt = input("Group by Family (F) or Item (I)? [F/I]: ").strip().lower()
        if group_opt in ['f', 'i']: break
        print("Invalid option. Please enter 'F' or 'I'.")
        
    yoy_grouping_col = yoy_config["data_source"]["grouping_column"] if group_opt == 'f' else yoy_config["data_source"]["item_column"]
    item_col = yoy_config["data_source"]["item_column"]

    # --- NUEVA FEATURE: Pregunta de Familias ---
    yoy_has_families = True
    if group_opt == 'f':
        print("\nDoes this file already have Families included? (Y/N)")
        print("WARNING: Deprecated feature going to disappear on a future release")
        fam_opt = input("").strip().upper()
        if fam_opt == 'N':
            yoy_has_families = False

    # --- PROTOCOLO APB: Validar Cabeceras ---
    try:
        df_headers = pd.read_excel(yoy_file_path, nrows=0)
        col_f = yoy_config["data_source"]["date_column"]
        col_c = yoy_config["data_source"]["quantity_column"]
        col_b = yoy_config["data_source"]["branch_column"]
        
        required_cols = [col_f, col_c, col_b]
        if group_opt == 'f':
            if yoy_has_families:
                required_cols.append(yoy_grouping_col)
            else:
                required_cols.append(item_col) # Necesario para generar la familia
        else:
            required_cols.append(item_col)

        faltantes = [c for c in required_cols if c not in df_headers.columns]
        if faltantes:
            log.error(f"APB File Validation: Missing columns {faltantes}")
            print(f"\n❌ APB Error: The file is missing these mandatory columns: {faltantes}")
            print("Check if you selected the correct Excel file or if reports.json is misconfigured.")
            input("Press Enter to return...")
            return
    except Exception as e:
        log.error(f"Could not read file headers: {e}")
        print("\n❌ APB Error: Could not read the file. Ensure it is not corrupted or open in another program.")
        input("Press Enter to return...")
        return

    while True:
        try:
            start_date_str = input("Start date (YYYY-MM-DD): ").strip()
            end_date_str = input("End date (YYYY-MM-DD): ").strip()
            
            yoy_start_dt = pd.to_datetime(start_date_str, format='%Y-%m-%d')
            yoy_end_dt = pd.to_datetime(end_date_str, format='%Y-%m-%d')
            
            if yoy_start_dt > yoy_end_dt:
                print("❌ APB Error: Start date cannot be later than end date! (Are you time traveling?).")
                continue
            break
        except ValueError:
            print("❌ APB Error: Incorrect format or invalid date. Use exactly YYYY-MM-DD (e.g., 2026-01-31).")
            
    yoy_end_dt = yoy_end_dt + pd.Timedelta(days=1, seconds=-1)
    
    while True:
        seg_opt = input("Do you want a segmented by month report? (Y/N) [N]: ").strip().lower()
        if seg_opt in ['y', 'n', '']: break
        print("Invalid option. Please enter 'Y' or 'N'.")
    yoy_segmented = (seg_opt == 'y')
    
    default_output = yoy_config.get("output_path", "analysis_report.xlsx")
    user_output = input(f"Output file name [Press Enter for '{default_output}']: ").strip()
    
    yoy_output_path = user_output if user_output else default_output
    if not yoy_output_path.lower().endswith(('.xlsx', '.xls')):
        yoy_output_path += '.xlsx'
    
    try:
        import time
        log.info("Starting YoY Sales Report generation pipeline...")
        start_time = time.time()
        final_out = generate_sales_report(yoy_file_path, yoy_output_path, yoy_start_dt, yoy_end_dt, yoy_config, yoy_grouping_col, yoy_segmented, yoy_has_families, yoy_profile)
        if final_out:
            elapsed = time.time() - start_time
            log.info(f"Report successfully generated at {final_out}")
            print(f"\n✅ Success: Report generated in {elapsed:.2f} seconds and saved to {final_out}")
    except Exception as e:
        log.error(f"Generating report: {e}")
        print(f"\n❌ Critical Error generating report: {e}")
        
    input("\nPress Enter to return to the main menu...")
