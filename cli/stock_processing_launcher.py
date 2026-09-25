"""
stock_processing_launcher.py — Stock Processing module launcher.

File paths are persisted to profiles/<profile>/last_paths.json and
pre-filled on the next run so the user does not retype them.
"""

import time
from argparse import Namespace

from cli.utils import (
    clear_screen, ask_file, validate_files_exist,
    load_last_paths, save_last_paths,
)
from core.logger import log, log_debug_event, log_exception
from core.system_utils import InvalidExcelOutputPathError, normalize_xlsx_output_path


def launch_stock_processing(active_profile: str) -> None:
    clear_screen()
    log_debug_event("stock_processing_cli_open", profile=active_profile)
    print(f"  📦  STOCK PROCESSING  —  Profile: [{active_profile}]\n")

    last = load_last_paths(active_profile)
    sp   = last.get("stock_processing", {})

    stock_file = ask_file("1. Raw stock spreadsheet",       sp.get("stock",  "stock_processing_raw_stock.xlsx"))
    cost_file  = ask_file("2. Cost price list",             sp.get("cost",   "shared_cost_list.xlsx"))
    sales_file = ask_file("3. Sales price list",            sp.get("sales",  "shared_sales_price_list.xlsx"))

    if not validate_files_exist([stock_file, cost_file, sales_file]):
        print("\n  ⚠️  Operation cancelled — required files are missing.")
        input("  Press Enter to return to the menu...")
        return

    out_file = ask_file("\n4. Output file name", sp.get("out", "Stock_Final_Report.xlsx"), is_output=True)
    try:
        out_file = normalize_xlsx_output_path(out_file)
    except InvalidExcelOutputPathError as exc:
        log.error("Invalid output path: %s", exc)
        print(f"\n  ❌ {exc}")
        input("  Press Enter to return to the menu...")
        return

    save_last_paths(active_profile, {
        "stock_processing": {
            "stock": stock_file,
            "cost":  cost_file,
            "sales": sales_file,
            "out":   out_file,
        }
    })

    log_debug_event(
        "stock_processing_cli_parameters",
        profile=active_profile,
        stock_file=stock_file,
        cost_file=cost_file,
        sales_file=sales_file,
        output_file=out_file,
    )
    print(f"\n  🚀 Processing inventory...  (Output: {out_file})")

    args = Namespace(
        stock_processing_raw=stock_file,
        shared_cost=cost_file,
        shared_sales=sales_file,
        stock_processing_out=out_file,
        stock_processing_profile=active_profile,
    )

    try:
        from engine.stock_processing.generator import run_stock_processing
        start = time.time()
        final_out = run_stock_processing(args)
        if final_out:
            elapsed = time.time() - start
            log_debug_event("stock_processing_cli_complete", output=final_out, elapsed_seconds=round(elapsed, 4))
            print(f"\n  ✅ Done in {elapsed:.2f}s  →  {final_out}")
    except ImportError as e:
        log_exception("Missing modules in 'engine/': %s", e)
    except Exception as e:
        log_exception("Critical Stock Processing error: %s", e)

    input("\n  Press Enter to return to the menu...")
