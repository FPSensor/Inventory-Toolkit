"""Single entry point for development commands."""
import argparse
import importlib
import sys


def main():
    parser = argparse.ArgumentParser(description="Inventory Toolkit developer tools")
    parser.add_argument("command", choices=("release", "integrity", "stress"))
    args, rest = parser.parse_known_args()
    modules = {"release": "release_check", "integrity": "integrity_check", "stress": "stress_tests"}
    sys.argv = [sys.argv[0], *rest]
    return importlib.import_module(f"debug_tools.{modules[args.command]}").main()


if __name__ == "__main__":
    raise SystemExit(main())
