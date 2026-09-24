"""
yoy_reports_launcher.py — Year-over-Year Sales Report launcher.

Uses ask_file() from utils instead of duplicating tkinter logic.
File paths are persisted between runs.
APB header validation is preserved intact.
"""

import time

import pandas as pd

from cli.utils import ask_file, load_last_paths, save_last_paths
from core.configuration_manager import ConfigurationManager
from core.logger import log


def launch_yoy_reports(active_profile: str) -> None:
    print("\n  📊  YEAR-OVER-YEAR SALES REPORT\n")

    profile = active_profile or "demo"
    cm = ConfigurationManager(profile=profile)
    yoy_config = cm.get_yoy_settings()

    if not yoy_config or "data_source" not in yoy_config:
        log.error(f"No valid report configuration found for profile '{profile}'.")
        print("  ❌ Check YoY Reports in the Configuration Hub (yoy_reports/settings.json).")
        input("  Press Enter to return...")
        return

    last = load_last_paths(profile)
    yoy_prev = last.get("yoy_reports", {})

    # ── Sales data file ──────────────────────────────────────────────────────
    yoy_file = ask_file("Sales data file", yoy_prev.get("file", ""))
    if not yoy_file:
        print("  ⚠️  No file selected — operation cancelled.")
        input("  Press Enter to return...")
        return

    # ── Grouping ─────────────────────────────────────────────────────────────
    while True:
        group_opt = input("  Group by Family (F) or Item (I)? [F/I]: ").strip().lower()
        if group_opt in ("f", "i"):
            break
        print("  ❌ Enter 'F' or 'I'.")

    ds = yoy_config["data_source"]
    yoy_grouping_col = ds["grouping_column"] if group_opt == "f" else ds["item_column"]
    item_col         = ds["item_column"]

    # ── Does the file already have the Family column? ────────────────────────
    yoy_has_families = True
    if group_opt == "f":
        resp = input("  Does the file already include the Family column? [Y/N]: ").strip().upper()
        yoy_has_families = resp != "N"

    # ── APB header validation ────────────────────────────────────────────────
    try:
        df_headers = pd.read_excel(yoy_file, nrows=0)
        required = [ds["date_column"], ds["quantity_column"], ds["branch_column"]]
        if group_opt == "f":
            required.append(yoy_grouping_col if yoy_has_families else item_col)
        else:
            required.append(item_col)

        missing = [c for c in required if c not in df_headers.columns]
        if missing:
            log.error(f"APB — Missing columns: {missing}")
            print(f"\n  ❌ APB Error: required columns are missing: {missing}")
            print("  Check that you selected the correct file, or verify YoY input columns in Configuration Hub.")
            input("  Press Enter to return...")
            return
    except Exception as e:
        log.error(f"Could not read file headers: {e}")
        print("\n  ❌ APB Error: could not read the file. Is it open in another application?")
        input("  Press Enter to return...")
        return

    # ── Date range ───────────────────────────────────────────────────────────
    while True:
        try:
            start_str = input("  Start date (YYYY-MM-DD): ").strip()
            end_str   = input("  End date   (YYYY-MM-DD): ").strip()
            yoy_start = pd.to_datetime(start_str, format="%Y-%m-%d")
            yoy_end   = pd.to_datetime(end_str,   format="%Y-%m-%d")
            if yoy_start > yoy_end:
                print("  ❌ Start date cannot be later than end date.")
                continue
            break
        except ValueError:
            print("  ❌ Invalid format — use YYYY-MM-DD (e.g. 2026-01-31).")

    yoy_end = yoy_end + pd.Timedelta(days=1, seconds=-1)

    # ── Report options ───────────────────────────────────────────────────────
    while True:
        seg_opt = input("  Generate segmented report by month? [Y/N, default N]: ").strip().lower()
        if seg_opt in ("y", "n", ""):
            break
        print("  ❌ Enter 'Y' or 'N'.")
    yoy_segmented = seg_opt == "y"

    while True:
        size_opt = input("  Include size breakdown? [Y/N, default N]: ").strip().lower()
        if size_opt in ("y", "n", ""):
            break
        print("  ❌ Enter 'Y' or 'N'.")
    yoy_include_sizes = size_opt == "y"

    # ── Output file ──────────────────────────────────────────────────────────
    default_out = yoy_config.get("output_path", "analysis_report.xlsx")
    out_path    = ask_file("Output file", yoy_prev.get("out", default_out), is_output=True)
    if not out_path.lower().endswith((".xlsx", ".xls")):
        out_path += ".xlsx"

    save_last_paths(profile, {
        "yoy_reports": {"file": yoy_file, "out": out_path}
    })

    # ── Generate ─────────────────────────────────────────────────────────────
    try:
        from engine.yoy_reports.generator import generate_sales_report
        log.info("Starting YoY report pipeline...")
        start = time.time()
        final_out = generate_sales_report(
            yoy_file,
            out_path,
            yoy_start,
            yoy_end,
            yoy_config,
            yoy_grouping_col,
            yoy_segmented,
            yoy_has_families,
            profile,
            yoy_include_sizes,
        )
        if final_out:
            elapsed = time.time() - start
            log.info(f"Report generated: {final_out}")
            print(f"\n  ✅ Done in {elapsed:.2f}s  →  {final_out}")
    except Exception as e:
        log.error(f"Error generating report: {e}")
        print(f"\n  ❌ Critical error: {e}")

    input("\n  Press Enter to return to the main menu...")
