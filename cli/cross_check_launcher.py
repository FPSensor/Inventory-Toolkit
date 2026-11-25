"""Inventory Cross Check in the console: ask, request the workflow, show the result."""

from dataclasses import replace

from cli.utils import ask_file, clear_screen, input_default, load_last_paths
from cli.workflow_runner import ask_option, confirm_column, run_job, show_notice, workflow_screen
from workflows import cross


def launch_cross_check(active_profile: str) -> None:
    clear_screen()
    print(f"  🔄  INVENTORY CROSS CHECK  —  Profile: [{active_profile}]\n")
    saved = load_last_paths(active_profile).get("cross_check", {})
    request = cross.CrossRequest(
        profile=active_profile,
        system=ask_file("1. System stock file", input_default(active_profile, saved.get("system"), "cross_check_system_stock.xls")),
        count=ask_file("2. Physical count file", input_default(active_profile, saved.get("count"), "cross_check_physical_count.xlsx")),
        cost=ask_file("3. Cost price list", input_default(active_profile, saved.get("cost"), "shared_cost_list.xlsx")),
        sales=ask_file("4. Sales price list", input_default(active_profile, saved.get("sales"), "shared_sales_price_list.xlsx")),
    )
    with workflow_screen(active_profile):
        columns = cross.check(request, confirm_column)
        request = replace(
            request,
            output=ask_file("\n5. Output file name", saved.get("out") or "Cross_Check_Results.xlsx", is_output=True),
            consolidate=ask_option("Consolidate quantities from multiple databases?"),
            partial_count=ask_option("Filter by scanned articles only (partial count)?"),
        )
        run_job(cross.prepare(request, columns, show_notice))
