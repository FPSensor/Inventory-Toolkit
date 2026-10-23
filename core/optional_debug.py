"""Capability-gated discovery without a mandatory debug-package import."""
from importlib import import_module, util

from core.build import BUILD


def debug_available():
    return BUILD.type == "debug" and util.find_spec("debug_tools") is not None


def open_debug_console():
    if not debug_available():
        return False
    import_module("debug_tools.console").developer_tools_menu()
    return True
