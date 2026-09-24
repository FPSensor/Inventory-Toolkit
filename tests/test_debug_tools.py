import sys
from types import SimpleNamespace

from cli import debug_menu
from cli import menu


def test_hidden_debug_selector_can_enable_level_three(monkeypatch):
    monkeypatch.setattr(menu, "clear_screen", lambda: None)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "3")
    assert menu._select_debug_level(1) == 3


def test_pytest_developer_action_uses_current_python(monkeypatch):
    calls = []

    def fake_run(command, cwd, check):
        calls.append((command, cwd, check))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(debug_menu.subprocess, "run", fake_run)
    assert debug_menu._run_pytest() == 0
    assert calls == [([sys.executable, "-m", "pytest", "-q"], debug_menu.ROOT, False)]
