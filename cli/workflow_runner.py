"""Run a shared workflow in the console and show how it ended."""

from contextlib import contextmanager

from cli.progress import show_progress, show_stats
from cli.utils import confirm_default_column
from cli.workflow_setup import recover_configuration
from core.configuration_errors import ConfigurationError
from core.logger import log_exception
from core.system_utils import InvalidExcelOutputPathError
from core.workflow_errors import WorkflowError


def confirm_column(_path, field, wanted, default) -> bool:
    return confirm_default_column(field, wanted, default)


def show_notice(message: str) -> None:
    print(f"  ⚠️  {message}")


def ask_option(question: str, default: bool = False) -> bool:
    hint = "Y/n" if default else "y/N"
    while True:
        answer = input(f"  {question} [{hint}]: ").strip().lower()
        if answer in ("y", "n", ""):
            return default if not answer else answer == "y"
        print("  Enter 'Y' or 'N'.")


@contextmanager
def workflow_screen(profile: str):
    """Explain any failure of the workflow and wait before returning to the menu."""
    try:
        yield
    except WorkflowError as exc:
        if not (exc.can_configure and recover_configuration(profile, exc)):
            print(f"\n  ❌ {exc}")
    except (ConfigurationError, InvalidExcelOutputPathError) as exc:
        print(f"\n  ❌ {exc}")
    except Exception as exc:
        log_exception("Critical workflow error: %s", exc)
    input("\n  Press Enter to return to the menu...")


def run_job(job) -> None:
    print(f"\n  🚀 Processing...  (Output: {job.request.output})")
    result = job.run(progress=show_progress, stats=show_stats, interactive=True)
    for warning in result.warnings:
        print(f"\n⚠️ {warning}")
    print(f"\n  ✅ Done in {result.elapsed:.2f}s  →  {result.output}")
