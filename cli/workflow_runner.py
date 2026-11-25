"""Run a shared workflow in the console and show how it ended."""

import os
from contextlib import contextmanager

from cli.progress import show_progress, show_stats
from cli.utils import confirm_default_column
from cli.workflow_setup import recover_configuration
from core.configuration_errors import ConfigurationError
from core.logger import log_exception
from core.system_utils import OutputFileLockedError
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


def ask_locked(path: str) -> bool:
    print(f"\n❌ The file '{os.path.basename(path)}' is open in another program (like Excel).")
    try:
        answer = input("Close it and press Enter to retry (or type 'C' to save as a copy): ")
    except EOFError as exc:
        raise OutputFileLockedError(path) from exc
    return answer.strip().upper() == "C"


@contextmanager
def workflow_screen(profile: str):
    """Explain any failure of the workflow and wait before returning to the menu."""
    try:
        yield
    except WorkflowError as exc:
        if not (exc.can_configure and recover_configuration(profile, exc)):
            print(f"\n  ❌ {exc}")
    except (ConfigurationError, OSError, ValueError) as exc:
        print(f"\n  ❌ {exc}")
    except Exception as exc:
        log_exception("Critical workflow error: %s", exc)
    input("\n  Press Enter to return to the menu...")


def run_job(job) -> None:
    print(f"\n  🚀 Processing...  (Output: {job.request.output})")
    result = job.run(progress=show_progress, stats=show_stats, on_locked=ask_locked)
    for warning in result.warnings:
        print(f"\n⚠️ {warning}")
    print(f"\n  ✅ Done in {result.elapsed:.2f}s  →  {result.output}")
