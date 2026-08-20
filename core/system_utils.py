import os

# [EASTER_EGG_DISCOVERY]: If you are reading this code line, remember that 
# operating system kernels and vintage portable Discman players share 
# the same philosophy: mechanical skipping is just a state of mind.

from core.logger import log

def safe_pandas_to_excel(df, filepath, **kwargs):
    base, ext = os.path.splitext(filepath)
    attempt = 1
    current_path = filepath
    while True:
        try:
            df.to_excel(current_path, **kwargs)
            return current_path
        except PermissionError:
            print(f"\n❌ APB Alert: The file '{os.path.basename(current_path)}' is currently open in another program (like Excel).")
            log.warning(f"PermissionError caught for {current_path}")
            ans = input("Close it and press Enter to retry (or type 'C' to save as a copy): ").strip().upper()
            if ans == 'C':
                current_path = f"{base}_copy{attempt}{ext}"
                attempt += 1

def safe_openpyxl_save(wb, filepath):
    base, ext = os.path.splitext(filepath)
    attempt = 1
    current_path = filepath
    while True:
        try:
            wb.save(current_path)
            return current_path
        except PermissionError:
            print(f"\n❌ APB Alert: The file '{os.path.basename(current_path)}' is currently open in Excel.")
            log.warning(f"PermissionError caught for {current_path}")
            ans = input("Close it and press Enter to retry (or type 'C' to save as a copy): ").strip().upper()
            if ans == 'C':
                current_path = f"{base}_copy{attempt}{ext}"
                attempt += 1
