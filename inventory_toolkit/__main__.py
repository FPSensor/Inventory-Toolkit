"""Select only an interface included by the build manifest."""
import argparse
import importlib
import importlib.util
import sys

from core.runtime.build import BUILD
from core.runtime.console import utf8_output


# Packages every report needs; the desktop checks its own.
REQUIRED_PACKAGES = ("pandas", "numpy", "openpyxl", "pydantic", "lxml")


def missing_packages() -> list[str]:
    return [name for name in REQUIRED_PACKAGES if importlib.util.find_spec(name) is None]


def _explain_missing_packages() -> bool:
    """Say how to install what is missing instead of failing with a traceback."""
    missing = missing_packages()
    if missing:
        print(
            f"Inventory Toolkit cannot start: these packages are not installed: {', '.join(missing)}.\n"
            "On Windows run 'Setup Environment.bat'; elsewhere run 'python -m pip install -r requirements.txt'. "
            "Then start Inventory Toolkit again.",
            file=sys.stderr,
        )
    return bool(missing)


def main(argv=None):
    utf8_output()
    argv = list(sys.argv[1:] if argv is None else argv)
    if (not argv or argv[0] not in {"-h", "--help", "--version"}) and _explain_missing_packages():
        return 1
    if argv and argv[0] in {'doctor', 'history'}:
        from inventory_toolkit.maintenance import main as maintenance
        return maintenance(argv)
    if argv and argv[0] == 'run':
        from inventory_toolkit.run import main as run
        return run(argv[1:])
    parser = argparse.ArgumentParser(description="Inventory Toolkit", epilog=
        "Unattended reports: run {stock,cross,yoy} --profile NAME. "
        "Profile maintenance: doctor --profile NAME; history {list,create,restore} --profile NAME")
    parser.add_argument("--interface", choices=("cli", "gui"), default=BUILD.default_control)
    parser.add_argument("--version", action="version", version=BUILD.version)
    args, remaining = parser.parse_known_args(argv)
    if not BUILD.supports(args.interface):
        parser.error(f"This build does not include the {args.interface.upper()} interface.")
    sys.argv = [sys.argv[0], *remaining]
    entry = "cli.menu:main" if args.interface == "cli" else "gui.app:launch_gui"
    module, function = entry.split(":")
    getattr(importlib.import_module(module), function)()


if __name__ == "__main__":
    raise SystemExit(main())
