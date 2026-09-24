"""Hidden developer, diagnostics, and release tools for debug level 3."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from cli.utils import clear_screen
from core.logger import get_session_log_path, log, log_debug_event

ROOT = Path(__file__).resolve().parents[1]


def _run_command(command: list[str], *, label: str) -> int:
    log_debug_event("developer_tool_start", label=label, command=command, cwd=str(ROOT))
    print("\n  Running:", " ".join(command), "\n")
    result = subprocess.run(command, cwd=ROOT, check=False).returncode
    log_debug_event("developer_tool_finish", label=label, returncode=result)
    return result


def _run_release_check(*arguments: str) -> int:
    return _run_command(
        [sys.executable, "tools/ReleaseCheck.py", *arguments],
        label=f"ReleaseCheck {' '.join(arguments) or 'quick'}",
    )


def _run_pytest() -> int:
    return _run_command(
        [sys.executable, "-m", "pytest", "-q"],
        label="pytest",
    )


def _pause(result: int, *, label: str = "Developer tool") -> None:
    status = "PASSED" if result == 0 else "FAILED"
    print(f"\n  {label} finished: {status}")
    input("  Press Enter to continue...")



def _show_session_log_tail(lines: int = 80) -> None:
    clear_screen()
    path = get_session_log_path()
    print(f"\n  SESSION LOG — last {lines} lines")
    print(f"  {path}\n")
    if not path.exists():
        print("  No session log has been created yet.")
    else:
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in content[-lines:]:
            print("  " + line)
    input("\n  Press Enter to return...")


def _confirm_reference_update() -> bool:
    clear_screen()
    print("\n  GOLDEN MASTER UPDATE\n")
    print("  This action replaces the approved release-reference workbooks.")
    print("  Use it only after deliberately changing business behavior, the")
    print("  demo fixture, or the demo profile and reviewing the new output.\n")
    print("  A normal failing release test is NOT a reason to update references.\n")
    confirmation = input("  Type UPDATE REFERENCES to continue: ").strip()
    return confirmation == "UPDATE REFERENCES"


# BEGIN LEGACY_COMPATIBILITY
def _legacy_compatibility_menu() -> None:
    """Audit or permanently retire the temporary compatibility layer."""
    retirement_tool = ROOT / "tools" / "RetireLegacyCompatibility.py"
    if not retirement_tool.exists():
        print("\n  Legacy compatibility has already been retired.")
        input("  Press Enter to continue...")
        return

    while retirement_tool.exists():
        clear_screen()
        print("\n  LEGACY COMPATIBILITY LIFECYCLE\n")
        print("    1  ›  Read-only retirement audit")
        print("    2  ›  Retire compatibility and validate (leave uncommitted)")
        print("    3  ›  Retire compatibility, validate, and create Git commit")
        print("    0  ›  Back\n")
        print("  Retirement is intentionally guarded. The tool refuses to run")
        print("  while profiles, callers, or the Git worktree are not ready.\n")

        option = input("  Choose an option: ").strip().upper()
        if option == "0":
            return
        if option == "1":
            _pause(
                _run_command(
                    [sys.executable, str(retirement_tool.relative_to(ROOT))],
                    label="legacy compatibility audit",
                ),
                label="Compatibility audit",
            )
            continue
        if option not in {"2", "3"}:
            continue

        clear_screen()
        print("\n  PERMANENT COMPATIBILITY RETIREMENT\n")
        print("  This removes pre-v3 migration/API compatibility from the repository.")
        print("  It does NOT delete archived _legacy_v1_backup data.")
        print("  Validation must pass before changes are kept.\n")
        confirmation = input("  Type RETIRE COMPATIBILITY to continue: ").strip()
        if confirmation != "RETIRE COMPATIBILITY":
            print("\n  Retirement cancelled.")
            input("  Press Enter to continue...")
            continue

        command = [
            sys.executable,
            str(retirement_tool.relative_to(ROOT)),
            "--apply",
        ]
        if option == "3":
            command.append("--commit")
        result = _run_command(command, label="legacy compatibility retirement")
        _pause(result, label="Compatibility retirement")

        # The retirement tool removes itself and strips this menu block from the
        # source tree. Checking the path also hides the option immediately from
        # this already-running Python process after a successful retirement.
        if result == 0 and not retirement_tool.exists():
            log.info("Legacy compatibility retired; its developer menu entry is now unavailable.")
            return
# END LEGACY_COMPATIBILITY


def developer_tools_menu() -> None:
    """Show the hidden developer console exposed only at debug level 3."""
    while True:
        clear_screen()
        print("\n  INVENTORY TOOLKIT — DEVELOPER CONSOLE (DEBUG LEVEL 3)\n")
        print("    1  ›  Run pytest")
        print("    2  ›  Quick repository verification")
        print("    3  ›  Demo workflow smoke test")
        print("    4  ›  Full release certification (golden masters)")
        print("    5  ›  Update golden-master references")
        print("    6  ›  Show current session log tail")
        # BEGIN LEGACY_COMPATIBILITY
        retirement_available = (ROOT / "tools" / "RetireLegacyCompatibility.py").exists()
        if retirement_available:
            print("    7  ›  Legacy compatibility lifecycle")
        # END LEGACY_COMPATIBILITY
        print("    0  ›  Back\n")

        option = input("  Choose an option: ").strip().upper()
        log_debug_event("developer_console_choice", option=option)
        if option == "0":
            return
        if option == "1":
            _pause(_run_pytest(), label="Pytest")
        elif option == "2":
            _pause(_run_release_check(), label="Quick verification")
        elif option == "3":
            _pause(_run_release_check("--demo"), label="Demo smoke test")
        elif option == "4":
            _pause(_run_release_check("--release"), label="Release certification")
        elif option == "5":
            if not _confirm_reference_update():
                print("\n  Reference update cancelled.")
                input("  Press Enter to continue...")
                continue
            _pause(
                _run_release_check("--update-reference", "--yes"),
                label="Golden-master update",
            )
        elif option == "6":
            _show_session_log_tail()
        # BEGIN LEGACY_COMPATIBILITY
        elif option == "7" and retirement_available:
            _legacy_compatibility_menu()
        # END LEGACY_COMPATIBILITY
