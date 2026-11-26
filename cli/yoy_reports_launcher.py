"""Year-over-Year reports in the console: ask, request the workflow, show the result."""

from dataclasses import replace

from cli.utils import ask_file, input_default
from core.profiles.profile_store import load_last_paths
from cli.workflow_runner import ask_option, confirm_column, run_job, show_notice, workflow_screen
from core.workflow_errors import WorkflowError
from workflows import yoy


def _ask_grouping() -> bool:
    while True:
        answer = input("  Group by Family (F) or Item (I)? [F/I]: ").strip().lower()
        if answer in ("f", "i"):
            return answer == "f"
        print("  ❌ Enter 'F' or 'I'.")


def _ask_period() -> tuple[str, str]:
    while True:
        dates = input("  Start date (YYYY-MM-DD): "), input("  End date   (YYYY-MM-DD): ")
        try:
            yoy.period(*dates)
            return dates
        except WorkflowError as exc:
            print(f"  ❌ {exc}")


def launch_yoy_reports(active_profile: str) -> None:
    print("\n  📊  YEAR-OVER-YEAR SALES REPORT\n")
    profile = active_profile or "demo"
    with workflow_screen(profile):
        output = yoy.settings(profile)["output"]
        saved = load_last_paths(profile).get("yoy_reports", {})
        request = yoy.YoYRequest(profile, ask_file("Sales data file", input_default(
            profile, saved.get("file"), "yoy_sales_history.xlsx", other_default="")))
        yoy.check_file(request)

        by_family = _ask_grouping()
        has_families = ask_option("Does the file already include the Family column?", True) if by_family else True
        sales_amounts = ask_option("Include sales amounts (revenue), in addition to units?")
        start, end = _ask_period()
        by_month = ask_option("Generate segmented report by month?")
        request = replace(
            request, by_family=by_family, has_families=has_families, sales_amounts=sales_amounts,
            start=start, end=end, by_month=by_month,
            annual_comparison=not by_month and ask_option("Include annual comparison below the full report?"),
            variants=ask_option("Include variant breakdown?", output.get("include_variants", False)),
        )
        config = yoy.check(request, confirm_column)
        request = replace(request, output=ask_file(
            "Output file", saved.get("out") or output["default_path"], is_output=True))
        run_job(yoy.prepare(request, config, show_notice))
