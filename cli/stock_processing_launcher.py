"""Stock Processing in the console: ask, request the workflow, show the result."""

from dataclasses import replace

from cli.utils import ask_file, clear_screen, input_default
from core.profiles.profile_store import load_last_paths
from cli.workflow_runner import ask_option, confirm_column, run_job, show_notice, workflow_screen
from workflows import stock


def launch_stock_processing(active_profile: str) -> None:
    clear_screen()
    print(f"  📦  STOCK PROCESSING  —  Profile: [{active_profile}]\n")
    saved = load_last_paths(active_profile).get("stock_processing", {})
    request = stock.StockRequest(
        profile=active_profile,
        stock=ask_file("1. Raw stock spreadsheet", input_default(active_profile, saved.get("stock"), "stock_processing_raw_stock.xlsx")),
        cost=ask_file("2. Cost price list", input_default(active_profile, saved.get("cost"), "shared_cost_list.xlsx")),
        sales=ask_file("3. Sales price list", input_default(active_profile, saved.get("sales"), "shared_sales_price_list.xlsx")),
    )
    with workflow_screen(active_profile):
        columns = stock.check(request, confirm_column)
        request = replace(
            request,
            output=ask_file("\n4. Output file name", saved.get("out") or "Stock_Final_Report.xlsx", is_output=True),
            unit_prices=ask_option("Include unit prices in the detail, in addition to totals?"),
        )
        run_job(stock.prepare(request, columns, show_notice))
