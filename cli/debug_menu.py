"""Debug-only developer and release tools for the CLI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from cli.utils import clear_screen

ROOT = Path(__file__).resolve().parents[1]


def _run_release_check(*arguments: str) -> int:
    command = [sys.executable, "tools/ReleaseCheck.py", *arguments]
    print("\n  Running:", " ".join(command), "\n")
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def _pause(result: int) -> None:
    status = "PASSED" if result == 0 else "FAILED"
    print(f"\n  Release tool finished: {status}")
    input("  Press Enter to continue...")


def _confirm_reference_update() -> bool:
    clear_screen()
    print("\n  GOLDEN MASTER UPDATE\n")
    print("  This action replaces the approved release-reference workbooks.")
    print("  Use it only after deliberately changing business behavior, the")
    print("  demo fixture, or the demo profile and reviewing the new output.\n")
    print("  A normal failing release test is NOT a reason to update references.\n")
    confirmation = input("  Type UPDATE REFERENCES to continue: ").strip()
    return confirmation == "UPDATE REFERENCES"


def developer_tools_menu() -> None:
    """Show developer-only verification tools exposed at debug level 3."""
    while True:
        clear_screen()
        print("\n  INVENTORY TOOLKIT — DEVELOPER / RELEASE TOOLS\n")
        print("    1  ›  Quick repository verification")
        print("    2  ›  Demo workflow smoke test")
        print("    3  ›  Full release certification (golden masters)")
        print("    4  ›  Update golden-master references")
        print("    5  ›  Audit legacy compatibility retirement")
        print("    0  ›  Back\n")

        option = input("  Choose an option: ").strip().upper()
        if option == "0":
            return
        if option == "1":
            _pause(_run_release_check())
        elif option == "2":
            _pause(_run_release_check("--demo"))
        elif option == "3":
            _pause(_run_release_check("--release"))
        elif option == "4":
            if not _confirm_reference_update():
                print("\n  Reference update cancelled.")
                input("  Press Enter to continue...")
                continue
            _pause(_run_release_check("--update-reference", "--yes"))
        elif option == "5":
            retirement_tool = ROOT / "tools" / "RetireLegacyCompatibility.py"
            if not retirement_tool.exists():
                print("\n  Legacy compatibility has already been retired.")
                input("  Press Enter to continue...")
                continue
            command = [sys.executable, str(retirement_tool.relative_to(ROOT))]
            print("\n  Running:", " ".join(command), "\n")
            result = subprocess.run(command, cwd=ROOT, check=False).returncode
            _pause(result)
