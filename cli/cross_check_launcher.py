"""
cross_check_launcher.py — Inventory Cross Check module launcher.

Remembers file paths used in the previous run so the user does not
have to retype them on every execution.
"""

import time
from argparse import Namespace

from cli.utils import (
    clear_screen, ask_file, validate_files_exist,
    load_last_paths, save_last_paths,
)
from core.logger import log, log_debug_event, log_exception


def launch_cross_check(active_profile: str) -> None:
    clear_screen()
    log_debug_event("cross_check_cli_open", profile=active_profile)
    print(f"  🔄  INVENTORY CROSS CHECK  —  Profile: [{active_profile}]\n")

    last = load_last_paths(active_profile)
    cc   = last.get("cross_check", {})

    system_file = ask_file("1. System stock file",          cc.get("system", "cross_check_system_stock.xls"))
    count_file  = ask_file("2. Physical count file",        cc.get("count",  "cross_check_physical_count.xlsx"))
    cost_file   = ask_file("3. Cost price list",            cc.get("cost",   "shared_cost_list.xlsx"))
    sales_file  = ask_file("4. Sales price list",           cc.get("sales",  "shared_sales_price_list.xlsx"))

    if not validate_files_exist([system_file, count_file, cost_file, sales_file]):
        print("\n  ⚠️  Operation cancelled — required files are missing.")
        input("  Press Enter to return to the menu...")
        return

    out_file = ask_file("\n5. Output file name", cc.get("out", "Cross_Check_Results.xlsx"), is_output=True)
    if not out_file.endswith((".xlsx", ".xls")):
        out_file += ".xlsx"

    save_last_paths(active_profile, {
        "cross_check": {
            "system": system_file,
            "count":  count_file,
            "cost":   cost_file,
            "sales":  sales_file,
            "out":    out_file,
        }
    })

    print("\n  ─ Cross Check options ─")
    resp_ds      = input("  Consolidate quantities from multiple databases? [Y/N, default N]: ").strip().upper()
    flag_consolidate = resp_ds == "Y"

    resp_partial = input("  Filter by scanned articles only (partial count)? [Y/N, default N]: ").strip().upper()
    flag_partial = resp_partial == "Y"

    log_debug_event(
        "cross_check_cli_parameters",
        profile=active_profile,
        system_file=system_file,
        count_file=count_file,
        cost_file=cost_file,
        sales_file=sales_file,
        output_file=out_file,
        consolidate=flag_consolidate,
        partial=flag_partial,
    )
    print(f"\n  🚀 Cross-checking data...  (Output: {out_file})")

    args = Namespace(
        cross_check_system=system_file,
        cross_check_count=count_file,
        shared_cost=cost_file,
        shared_sales=sales_file,
        cross_check_out=out_file,
        cross_check_profile=active_profile,
        cross_check_consolidate=flag_consolidate,
        cross_check_partial=flag_partial,
    )

    try:
        from engine.inventory_cross_check.generator import run_cross_check
        start = time.time()
        final_out = run_cross_check(args)
        if final_out:
            elapsed = time.time() - start
            log_debug_event("cross_check_cli_complete", output=final_out, elapsed_seconds=round(elapsed, 4))
            print(f"\n  ✅ Done in {elapsed:.2f}s  →  {final_out}")
    except ImportError as e:
        log_exception("Missing modules: %s", e)
    except Exception as e:
        log_exception("Critical Cross Check error: %s", e)

    input("\n  Press Enter to return to the menu...")
