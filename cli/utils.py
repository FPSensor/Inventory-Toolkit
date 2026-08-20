import os
import sys
import json
import subprocess
import tkinter as tk
from tkinter import filedialog
from core.logger import log

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def ask_yes_no(message):
    while True:
        response = input(f"{message} [Y/N]: ").strip().upper()
        if response == 'Y': return True
        if response == 'N': return False
        print("❌ Invalid option. Enter 'Y' for Yes or 'N' for No.")

def ask_file(message, default_val, is_output=False):
    response = input(f"{message} (Enter: '{default_val}', 'B' for Browser): ").strip()
    
    if response.upper() == 'B':
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        
        if is_output:
            path = filedialog.asksaveasfilename(
                title="Save result as...",
                initialfile=default_val,
                defaultextension=".xlsx",
                filetypes=[("Excel Files", "*.xlsx *.xls")]
            )
        else:
            path = filedialog.askopenfilename(
                title="Select file",
                filetypes=[("Excel Files", "*.xlsx *.xls"), ("All files", "*.*")]
            )
        root.destroy()
        
        if path:
            print(f"📁 Selected file: {path}")
            return path
        else:
            print(f"⚠️ Selection cancelled. Using default value.")
            return default_val
    return response if response else default_val

def validate_files_exist(file_list):
    all_exist = True
    for file_path in file_list:
        if file_path and not os.path.isfile(file_path):
            log.error(f"File '{file_path}' does not exist.")
            all_exist = False
    return all_exist

def open_in_editor(path):
    print(f"Opening {os.path.basename(path)} in default editor...")
    try:
        if sys.platform.startswith('darwin'):
            subprocess.call(('open', path))
        elif os.name == 'nt':
            os.startfile(path)
        elif os.name == 'posix':
            subprocess.call(('xdg-open', path))
    except Exception as e:
        log.error(f"Could not open file automatically: {e}")
    input("\nPress Enter when you have finished editing and saved your changes...")

def load_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        log.error(f"File {path} is corrupted or not valid JSON.")
        return None

def save_json(path, data):
    try:
        with open(path, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=4, ensure_ascii=False)
    except Exception as e:
        log.error(f"Error saving file: {e}")
