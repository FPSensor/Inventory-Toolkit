"""Source-checkout entry point for debug_tools.console."""
from pathlib import Path
import importlib
import sys

root = str(Path(__file__).resolve().parents[1])
if root not in sys.path:
    sys.path.insert(0, root)
module = importlib.import_module("debug_tools.console")
if __name__ == "__main__":
    raise SystemExit(module.main())
else:
    sys.modules[__name__] = module
