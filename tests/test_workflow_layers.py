"""Interfaces ask workflows; they never prepare or call an engine themselves."""
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

def imports(package, forbidden):
    found = set()
    for path in sorted((ROOT / package).rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = [node.module or ""] if isinstance(node, ast.ImportFrom) else (
                [alias.name for alias in node.names] if isinstance(node, ast.Import) else [])
            found |= {(path.relative_to(ROOT).as_posix(), name) for name in names if name.split(".")[0] in forbidden}
    return found


@pytest.mark.parametrize("package, forbidden", [
    ("core", {"engine", "workflows", "cli", "gui"}),
    ("engine", {"workflows", "cli", "gui"}),
    ("workflows", {"cli", "gui", "tkinter", "customtkinter"}),
    ("cli", {"gui", "engine"}), ("gui", {"cli", "engine"}),
])
def test_layers_only_depend_on_the_ones_below(package, forbidden):
    assert imports(package, forbidden) == set()


def test_workflows_never_talk_to_a_terminal():
    calls = {
        (path.name, node.func.id) for path in (ROOT / "workflows").rglob("*.py")
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"print", "input"}
    }
    assert calls == set()
