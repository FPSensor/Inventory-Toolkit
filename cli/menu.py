import sys
import argparse
from cli.utils import clear_screen
from cli.profiles import select_profile
from cli.config_menu import configuration_menu
from cli.cross_check_launcher import launch_cross_check
from cli.stock_processing_launcher import launch_stock_processing
from cli.yoy_reports_launcher import launch_yoy_reports
from cli.wizard import PANDAS_AVAILABLE
from cli.debug_menu import developer_tools_menu
from core.logger import log, log_debug_event, set_debug_level

try:
    from engine import stock_processing
    from engine import inventory_cross_check
    MODULES_LOADED = True
except ImportError as e:
    MODULES_LOADED = False
    _import_error = e

_VERSION = "1.4.0"

_LOGO = r"""
  ██╗███╗   ██╗██╗   ██╗███████╗███╗   ██╗████████╗ ██████╗ ██████╗ ██╗   ██╗
  ██║████╗  ██║██║   ██║██╔════╝████╗  ██║╚══██╔══╝██╔═══██╗██╔══██╗╚██╗ ██╔╝
  ██║██╔██╗ ██║██║   ██║█████╗  ██╔██╗ ██║   ██║   ██║   ██║██████╔╝ ╚████╔╝
  ██║██║╚██╗██║╚██╗ ██╔╝██╔══╝  ██║╚██╗██║   ██║   ██║   ██║██╔══██╗  ╚██╔╝
  ██║██║ ╚████║ ╚████╔╝ ███████╗██║ ╚████║   ██║   ╚██████╔╝██║  ██║   ██║
  ╚═╝╚═╝  ╚═══╝  ╚═══╝  ╚══════╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝   ╚═╝
                          T O O L K I T
"""

# Inner width (characters between the vertical borders) of the menu box.
_BOX_WIDTH = 50


def _row(text: str = "") -> str:
    """Return a single menu row padded to the box width, with side borders.

    Using a helper guarantees every row lines up regardless of the label
    length, so the right-hand border never drifts out of alignment.
    """
    return "  ║" + text.ljust(_BOX_WIDTH) + "║"


def _rule(left: str = "╠", right: str = "╣") -> str:
    """Return a horizontal separator line for the menu box."""
    return "  " + left + ("═" * _BOX_WIDTH) + right


def _centered(text: str) -> str:
    """Return a centered menu row."""
    return _row(text.center(_BOX_WIDTH))


def _draw_menu(current_profile: str, debug_level: int = 1) -> None:
    clear_screen()
    print(_LOGO)
    print(_rule("╔", "╗"))
    print(_centered(f"INVENTORY TOOLKIT  v{_VERSION}"))
    print(_rule())
    print(_row(f"   Active profile: [{current_profile}]"))
    if debug_level > 1:
        print(_row(f"   Debug diagnostics: [LEVEL {debug_level}]"))
    print(_rule())
    print(_row())
    print(_row("    C  ›  Inventory Cross Check"))
    print(_row("    S  ›  Stock Processing"))
    print(_row("    R  ›  YoY Sales Report"))
    print(_row())
    print(_rule())
    print(_row("    K  ›  Configuration"))
    print(_row("    P  ›  Change Profile"))
    if debug_level == 3:
        print(_row("    D  ›  Developer / Release Tools"))
    print(_row("    E  ›  Exit"))
    print(_rule("╚", "╝"))
    print()





def _select_debug_level(current_level: int) -> int:
    """Hidden runtime selector opened by typing ``debug`` in the main menu."""
    while True:
        clear_screen()
        print("\n  INVENTORY TOOLKIT — DEBUG VERBOSITY\n")
        print(f"  Current level: {current_level}\n")
        print("    1  ›  Operator mode      — errors only")
        print("    2  ›  Diagnostics        — operations, warnings, compatibility notices")
        print("    3  ›  Forensic mode      — detailed execution trace + Developer Console")
        print("    0  ›  Cancel\n")
        option = input("  Select debug level: ").strip()
        if option == "0" or option == "":
            return current_level
        if option in {"1", "2", "3"}:
            return int(option)
        print("  Invalid level. Choose 1, 2, 3, or 0.")
        input("  Press Enter to continue...")


def _apply_debug_level(level: int, *, reset_session_log: bool = False) -> int:
    """Apply logger and temporary compatibility diagnostics without restarting."""
    active_level = set_debug_level(level, reset_session_log=reset_session_log)
    # BEGIN LEGACY_COMPATIBILITY
    from core.compatibility import configure_compatibility_diagnostics

    configure_compatibility_diagnostics(active_level > 1)
    # END LEGACY_COMPATIBILITY
    return active_level

def _show_easter_egg() -> None:
    """Display the intentionally undocumented answer to an undocumented option."""
    clear_screen()
    print("\n  🥚  INVENTORY TOOLKIT / 42\n")
    print("  Longest prefix wins.")
    print("  The scanner may improvise; the master stock does not.")
    print("  Somewhere, a Discman is still trying to seek track 2.\n")
    input("  Press Enter to return...")

def main():
    parser = argparse.ArgumentParser(description="Inventory Toolkit CLI")
    parser.add_argument('-debug_level', '--debug-level', dest='debug_level', type=int, choices=[1, 2, 3], default=1,
                        help=argparse.SUPPRESS)
    args, _ = parser.parse_known_args()

    if not PANDAS_AVAILABLE:
        print("  ⚠️  Warning: Pandas is not installed.")

    if not MODULES_LOADED:
        print(f"  ⚠️  Warning: Could not load engine modules ({_import_error}).")
        input("  Press Enter to continue in degraded mode...")

    debug_level = _apply_debug_level(args.debug_level, reset_session_log=True)
    log_debug_event(
        "cli_start",
        version=_VERSION,
        debug_level=debug_level,
        modules_loaded=MODULES_LOADED,
        pandas_available=PANDAS_AVAILABLE,
    )
    if debug_level > 1:
        log.info("Inventory Toolkit %s starting (debug level %s)...", _VERSION, debug_level)

    current_profile = select_profile(None, is_startup=True)
    log_debug_event("profile_selected", profile=current_profile, startup=True)

    try:
        while True:
            _draw_menu(current_profile, debug_level)
            option = input("  Choose an option: ").strip().upper()
            log_debug_event("main_menu_choice", option=option, profile=current_profile)

            if option == "C":
                launch_cross_check(current_profile)
            elif option == "S":
                launch_stock_processing(current_profile)
            elif option == "R":
                launch_yoy_reports(current_profile)
            elif option == "K":
                configuration_menu(current_profile)
            elif option == "P":
                current_profile = select_profile(current_profile)
                log_debug_event("profile_selected", profile=current_profile, startup=False)
            elif option == "DEBUG":
                requested_level = _select_debug_level(debug_level)
                if requested_level != debug_level:
                    debug_level = _apply_debug_level(requested_level)
                    log.info("Runtime debug level is now %s.", debug_level)
            elif option == "D" and debug_level == 3:
                developer_tools_menu()
            elif option == "42":
                _show_easter_egg()
            elif option == "E":
                clear_screen()
                print("  Goodbye!\n")
                sys.exit(0)

    except KeyboardInterrupt:
        print("\n\n  Operation interrupted. Exiting safely...")
        sys.exit(0)
