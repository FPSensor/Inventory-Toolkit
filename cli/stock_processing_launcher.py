"""Stock Processing in the console: ask, request the workflow, show the result."""

from dataclasses import replace

from cli.progress import show_progress, show_stats
from cli.utils import ask_file, clear_screen, confirm_default_column, input_default, load_last_paths
from core.logger import log_debug_event, log_exception
from core.system_utils import InvalidExcelOutputPathError
from core.workflow_errors import WorkflowError
from workflows import stock


def _ask_unit_prices() -> bool:
    while True:
        answer = input("  Include unit prices in the detail, in addition to totals? [y/N]: ").strip().lower()
        if answer in ("y", "n", ""):
            return answer == "y"
        print("  Enter 'Y' or 'N'.")


def launch_stock_processing(active_profile: str) -> None:
    clear_screen()
    log_debug_event("stock_processing_cli_open", profile=active_profile)
    print(f"  📦  STOCK PROCESSING  —  Profile: [{active_profile}]\n")
    saved = load_last_paths(active_profile).get("stock_processing", {})

    request = stock.StockRequest(
        profile=active_profile,
        stock=ask_file("1. Raw stock spreadsheet", input_default(active_profile, saved.get("stock"), "stock_processing_raw_stock.xlsx")),
        cost=ask_file("2. Cost price list", input_default(active_profile, saved.get("cost"), "shared_cost_list.xlsx")),
        sales=ask_file("3. Sales price list", input_default(active_profile, saved.get("sales"), "shared_sales_price_list.xlsx")),
    )
    try:
        columns = stock.check(request, lambda _path, *question: confirm_default_column(*question))
        request = replace(
            request,
            output=ask_file("\n4. Output file name", saved.get("out") or "Stock_Final_Report.xlsx", is_output=True),
            unit_prices=_ask_unit_prices(),
        )
        job = stock.prepare(request, columns, notify=lambda message: print(f"  ⚠️  {message}"))
        print(f"\n  🚀 Processing inventory...  (Output: {job.request.output})")
        result = job.run(progress=show_progress, stats=show_stats, interactive=True)
        for warning in result.warnings:
            print(f"\n⚠️ {warning}")
        print(f"\n  ✅ Done in {result.elapsed:.2f}s  →  {result.output}")
    except (WorkflowError, InvalidExcelOutputPathError) as exc:
        print(f"\n  ❌ {exc}")
    except Exception as exc:
        log_exception("Critical Stock Processing error: %s", exc)

    input("\n  Press Enter to return to the menu...")
