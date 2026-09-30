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


def test_retirement_removes_documentation_links_and_preserves_current_resources(tmp_path, monkeypatch):
    import re
    import shutil

    tool = _load_tool()
    source_root = tool.ROOT
    for relative in (*tool.MARKER_FILES, *tool.COMPATIBILITY_MODULES, *tool.RETIRE_WITH_COMPATIBILITY):
        source = source_root / relative
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    sentinels = [
        "profiles/test/configs/_legacy_v1_backup/config.json",
        "core/resources/profile_defaults.json",
        "engine/current.py",
    ]
    for name in sentinels:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"retained\n")
    monkeypatch.setattr(tool, "ROOT", tmp_path)
    tool.apply_retirement()
    for relative in tool.MARKER_FILES:
        path = tmp_path / relative
        text = path.read_text(encoding="utf-8")
        assert "BEGIN LEGACY_COMPATIBILITY" not in text
        if path.suffix == ".md":
            assert "RetireLegacyCompatibility.py" not in text
            assert "legacy_compatibility.md" not in text
            for target in re.findall(r"\]\(([^)]+)\)", text):
                if not target.startswith(("http:", "https:", "#")):
                    assert (source_root / relative.parent / target.split("#")[0]).exists(), target
    for name in sentinels:
        assert (tmp_path / name).read_bytes() == b"retained\n"
    assert not (tmp_path / "tools/RetireLegacyCompatibility.py").exists()


def test_retirement_commit_has_author_title_and_description(monkeypatch):
    tool = _load_tool()
    staged = []
    calls = []
    monkeypatch.setattr(tool, "run_git", lambda *args: staged.append(args))
    monkeypatch.setattr(tool.subprocess, "run", lambda command, **kwargs: calls.append((command, kwargs)))
    tool.commit_retirement()
    assert staged == [("add", "-A")]
    command, kwargs = calls[0]
    assert command[command.index("--author") + 1] == "FPSensor <gkartyt@gmail.com>"
    paragraphs = [command[index + 1] for index, value in enumerate(command) if value == "-m"]
    assert paragraphs[0] == "core: compatibility: retire legacy configuration support"
    assert "previously" in paragraphs[1]
    assert "Current schema-v3 validation remains active" in paragraphs[1]
    assert "_legacy_v1_backup data is preserved" in paragraphs[1]
    assert kwargs["check"] is True
