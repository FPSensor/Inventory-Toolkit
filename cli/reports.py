import os
import pandas as pd
import tkinter as tk
from tkinter import filedialog
from core.configuration_manager import ConfigurationManager
from engine.reports.generator import generate_sales_report

def menu_reports(perfil_actual):
    print("\n--- Year-over-Year Sales Report Generation ---")
    
    profile = perfil_actual if perfil_actual else 'demo'
    
    cm = ConfigurationManager(profile=profile)
    config_report = cm.get_reports()
    
    if not config_report or "data_source" not in config_report:
        print(f"Error: No valid report configuration found for profile '{profile}'.")
        input("Press Enter to return...")
        return
            
    file_path = input("Enter sales file path (or press 'B' to browse): ").strip()
    
    if file_path.lower() == 'b':
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        file_path = filedialog.askopenfilename(title="Select File", filetypes=[("Excel", "*.xlsx *.xls")])
        root.destroy()
        if not file_path:
            return
            
    while True:
        group_opt = input("Group by Family (F) or Item (I)? [F/I]: ").strip().lower()
        if group_opt in ['f', 'i']:
            break
        print("Invalid option. Please enter 'F' or 'I'.")
        
    grouping_col = config_report["data_source"]["grouping_column"] if group_opt == 'f' else config_report["data_source"]["item_column"]

    # ACA ESTA LA MAGIA DEL FRENO TEMPORAL
    while True:
        try:
            start_date_str = input("Start date (YYYY-MM-DD): ").strip()
            end_date_str = input("End date (YYYY-MM-DD): ").strip()
            start_dt = pd.to_datetime(start_date_str)
            end_dt = pd.to_datetime(end_date_str)
            
            if start_dt > end_dt:
                print("? Error: The start date cannot be later than the end date.")
                continue
                
            break
        except ValueError:
            print("? Invalid date format. Please use YYYY-MM-DD.")
            
    end_dt = end_dt + pd.Timedelta(days=1, seconds=-1)
    
    while True:
        seg_opt = input("Do you want a segmented by month report? (Y/N) [N]: ").strip().lower()
        if seg_opt in ['y', 'n', '']:
            break
        print("Invalid option. Please enter 'Y' or 'N'.")
    segmented = (seg_opt == 'y')
    
    default_output = config_report.get("output_path", "analysis_report.xlsx")
    user_output = input(f"Output file name [Press Enter for '{default_output}']: ").strip()
    
    output_path = user_output if user_output else default_output
    if not output_path.lower().endswith(('.xlsx', '.xls')):
        output_path += '.xlsx'
    
    try:
        generate_sales_report(file_path, output_path, start_dt, end_dt, config_report, grouping_col, segmented)
        print(f"\nSuccess: Report saved to {output_path}")
    except Exception as e:
        print(f"\nError generating report: {e}")
        
    input("\nPress Enter to return to the main menu...")
