"""Regression coverage for the optional compatibility retirement tool."""

import importlib.util
from pathlib import Path

import pytest


def _load_tool():
    path = Path(__file__).resolve().parents[1] / "tools/RetireLegacyCompatibility.py"
    spec = importlib.util.spec_from_file_location("retirement_tool", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_retirement_preserves_surviving_line_bytes(tmp_path, newline):
    tool = _load_tool()
    path = tmp_path / "source.py"
    before = newline.join([
        "# retained UTF-8: \u03bb",
        "# BEGIN LEGACY_COMPATIBILITY",
        "obsolete = True",
        "# END LEGACY_COMPATIBILITY",
        "current = True",
        "",
    ]).encode("utf-8")
    path.write_bytes(before)
    tool.rewrite_text(path, lambda text: tool.strip_compatibility_blocks(text, path))
    assert path.read_bytes() == newline.join([
        "# retained UTF-8: \u03bb", "current = True", "",
    ]).encode("utf-8")


def test_retirement_preserves_mixed_newlines_and_missing_final_newline(tmp_path):
    tool = _load_tool()
    path = tmp_path / "source.py"
    path.write_bytes(b"keep\r\n# BEGIN LEGACY_COMPATIBILITY\nremove\r\n# END LEGACY_COMPATIBILITY\nlast")
    tool.rewrite_text(path, lambda text: tool.strip_compatibility_blocks(text, path))
    assert path.read_bytes() == b"keep\r\nlast"
