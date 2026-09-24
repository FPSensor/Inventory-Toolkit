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
    parser.add_argument('-debug_level', type=int, choices=[1, 2, 3], default=1,
                        help=argparse.SUPPRESS)
    args, _ = parser.parse_known_args()

    if not PANDAS_AVAILABLE:
        print("  ⚠️  Warning: Pandas is not installed.")

    if not MODULES_LOADED:
        print(f"  ⚠️  Warning: Could not load engine modules ({_import_error}).")
        input("  Press Enter to continue in degraded mode...")

    from core.logger import setup_logger
    log = setup_logger(args.debug_level)

    # BEGIN LEGACY_COMPATIBILITY
    from core.compatibility import configure_compatibility_diagnostics

    configure_compatibility_diagnostics(args.debug_level > 1)
    # END LEGACY_COMPATIBILITY

    if args.debug_level > 1:
        log.info(f"Inventory Toolkit {_VERSION} starting (debug level {args.debug_level})...")

    current_profile = select_profile(None, is_startup=True)

    try:
        while True:
            _draw_menu(current_profile, args.debug_level)
            option = input("  Choose an option: ").strip().upper()

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
            elif option == "D" and args.debug_level == 3:
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
