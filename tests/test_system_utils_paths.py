"""Paths pasted with the quotes that Windows "Copy as path" adds."""

import pytest

from core.files.system_utils import unquote_path


@pytest.mark.parametrize("typed, path", [
    ('"C:\\Stock\\hoy.xlsx"', "C:\\Stock\\hoy.xlsx"),
    ("'C:\\Stock\\hoy.xlsx'", "C:\\Stock\\hoy.xlsx"),
    ('  "/tmp/a b.xlsx"  ', "/tmp/a b.xlsx"),
    ("C:\\Stock\\hoy.xlsx", "C:\\Stock\\hoy.xlsx"),
    ('"half.xlsx', '"half.xlsx'),
    ("", ""),
])
def test_quotes_around_a_path_are_removed(typed, path):
    assert unquote_path(typed) == path


def test_cli_accepts_a_quoted_path(monkeypatch):
    from cli import utils

    monkeypatch.setattr("builtins.input", lambda prompt: '"C:\\Descargas\\stock.xlsx"')
    assert utils.ask_file("Stock", "default.xlsx") == "C:\\Descargas\\stock.xlsx"


def test_redirected_windows_output_can_print_symbols(monkeypatch):
    import io
    import sys

    from core.runtime.console import utf8_output

    redirected = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", redirected)
    utf8_output()
    print("⚠️ 3 products ✅")
    redirected.flush()
    assert redirected.buffer.getvalue().decode("utf-8").strip() == "⚠️ 3 products ✅"
