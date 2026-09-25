"""Year-over-Year Sales Report launcher.

File paths are persisted between runs and APB header validation happens before
starting the report engine.
"""

import time

import pandas as pd

from cli.utils import ask_file, load_last_paths, save_last_paths
from core.configuration_manager import ConfigurationManager
from core.logger import log, log_debug_event, log_exception
from engine.yoy_reports.metrics import resolve_metric_specs


def launch_yoy_reports(active_profile: str) -> None:
    print("\n  📊  YEAR-OVER-YEAR SALES REPORT\n")
    log_debug_event("yoy_cli_open", profile=active_profile)

    profile = active_profile or "demo"
    config = ConfigurationManager(profile=profile)
    yoy_config = config.get_yoy_reports_config()

    if not yoy_config or "input" not in yoy_config:
        log.error("No valid report configuration found for profile '%s'.", profile)
        print("  ❌ Check YoY Reports in the Configuration Hub (yoy_reports/settings.json).")
        input("  Press Enter to return...")
        return

    last_paths = load_last_paths(profile)
    previous_paths = last_paths.get("yoy_reports", {})

    sales_file = ask_file("Sales data file", previous_paths.get("file", ""))
    if not sales_file:
        print("  ⚠️  No file selected — operation cancelled.")
        input("  Press Enter to return...")
        return

    while True:
        grouping_option = input("  Group by Family (F) or Item (I)? [F/I]: ").strip().lower()
        if grouping_option in ("f", "i"):
            break
        print("  ❌ Enter 'F' or 'I'.")

    input_config = yoy_config["input"]
    grouping_column = (
        input_config["grouping_column"]
        if grouping_option == "f"
        else input_config["item_column"]
    )
    item_column = input_config["item_column"]

    has_families = True
    if grouping_option == "f":
        response = input(
            "  Does the file already include the Family column? [Y/N]: "
        ).strip().upper()
        has_families = response != "N"

    try:
        header_frame = pd.read_excel(sales_file, nrows=0)
        metric_specs = resolve_metric_specs(yoy_config)
        required_columns = [
            input_config["date_column"],
            input_config["branch_column"],
            *(metric.column for metric in metric_specs),
        ]
        if grouping_option == "f":
            required_columns.append(grouping_column if has_families else item_column)
        else:
            required_columns.append(item_column)
        required_columns = list(dict.fromkeys(required_columns))

        missing_columns = [
            column for column in required_columns if column not in header_frame.columns
        ]
        if missing_columns:
            log.error("APB — Missing columns: %s", missing_columns)
            print(f"\n  ❌ APB Error: required columns are missing: {missing_columns}")
            print(
                "  Check that you selected the correct file, or verify YoY input "
                "columns in Configuration Hub."
            )
            input("  Press Enter to return...")
            return
    except Exception as exc:
        log.error("Could not read file headers: %s", exc)
        print("\n  ❌ APB Error: could not read the file. Is it open in another application?")
        input("  Press Enter to return...")
        return

    while True:
        try:
            start_text = input("  Start date (YYYY-MM-DD): ").strip()
            end_text = input("  End date   (YYYY-MM-DD): ").strip()
            start_date = pd.to_datetime(start_text, format="%Y-%m-%d")
            end_date = pd.to_datetime(end_text, format="%Y-%m-%d")
            if start_date > end_date:
                print("  ❌ Start date cannot be later than end date.")
                continue
            break
        except ValueError:
            print("  ❌ Invalid format — use YYYY-MM-DD (e.g. 2026-01-31).")

    end_date = end_date + pd.Timedelta(days=1, seconds=-1)

    while True:
        segmented_option = input(
            "  Generate segmented report by month? [Y/N, default N]: "
        ).strip().lower()
        if segmented_option in ("y", "n", ""):
            break
        print("  ❌ Enter 'Y' or 'N'.")
    segmented = segmented_option == "y"

    configured_include_sizes = yoy_config.get("output", {}).get("include_sizes", False)
    size_default = "Y" if configured_include_sizes else "N"
    while True:
        size_option = input(
            f"  Include size breakdown? [Y/N, default {size_default} from profile]: "
        ).strip().lower()
        if size_option in ("y", "n", ""):
            break
        print("  ❌ Enter 'Y' or 'N'.")
    include_sizes = (
        configured_include_sizes if size_option == "" else size_option == "y"
    )

    default_output = yoy_config.get("output", {}).get(
        "default_path",
        "analysis_report.xlsx",
    )
    output_path = ask_file(
        "Output file",
        previous_paths.get("out", default_output),
        is_output=True,
    )
    if not output_path.lower().endswith((".xlsx", ".xls")):
        output_path += ".xlsx"

    save_last_paths(
        profile,
        {"yoy_reports": {"file": sales_file, "out": output_path}},
    )
    log_debug_event(
        "yoy_cli_parameters",
        profile=profile,
        sales_file=sales_file,
        output_file=output_path,
        grouping_column=grouping_column,
        grouping_mode=grouping_option,
        has_families=has_families,
        segmented=segmented,
        include_sizes=include_sizes,
        start=str(start_date),
        end=str(end_date),
    )

    try:
        from engine.yoy_reports.generator import generate_sales_report

        log.info("Starting YoY report pipeline...")
        started_at = time.time()
        final_output = generate_sales_report(
            sales_file,
            output_path,
            start_date,
            end_date,
            yoy_config,
            grouping_column,
            segmented,
            has_families,
            profile,
            include_sizes,
        )
        if final_output:
            elapsed = time.time() - started_at
            log.info("Report generated: %s", final_output)
            log_debug_event("yoy_cli_complete", output=final_output, elapsed_seconds=round(elapsed, 4))
            print(f"\n  ✅ Done in {elapsed:.2f}s  →  {final_output}")
    except Exception as exc:
        log_exception("Error generating report: %s", exc)
        print(f"\n  ❌ Critical error: {exc}")

    input("\n  Press Enter to return to the main menu...")
