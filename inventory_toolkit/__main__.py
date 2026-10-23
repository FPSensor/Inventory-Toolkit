"""Select only an interface included by the build manifest."""
import argparse
import importlib
import sys

from core.build import BUILD


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in {'doctor', 'history'}:
        from inventory_toolkit.maintenance import main as maintenance
        return maintenance(argv)
    parser = argparse.ArgumentParser(description="Inventory Toolkit", epilog=
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
