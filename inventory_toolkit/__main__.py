"""Select only an interface included by the build manifest."""
import argparse
import importlib

from core.build import BUILD


def main():
    parser = argparse.ArgumentParser(description="Inventory Toolkit")
    parser.add_argument("--interface", choices=("cli", "gui"), default=BUILD.default_control)
    parser.add_argument("--version", action="version", version=BUILD.version)
    args, remaining = parser.parse_known_args()
    BUILD.require(args.interface)
    import sys
    sys.argv = [sys.argv[0], *remaining]
    entry = "cli.menu:main" if args.interface == "cli" else "gui.app:launch_gui"
    module, function = entry.split(":")
    getattr(importlib.import_module(module), function)()


if __name__ == "__main__":
    main()
