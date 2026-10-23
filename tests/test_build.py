from pathlib import Path

import pytest

from core.build import load_build


def test_manifest_capabilities_and_validation(tmp_path):
    path = tmp_path / "build.prop"
    path.write_text("ver=v9.2\ntype=release\ncontrol-type=cli\ndefault-control=cli\ngui-stage=RC\n")
    build = load_build(path)
    assert build.version == "9.2" and build.supports("cli") and not build.supports("gui")
    with pytest.raises(RuntimeError, match="does not include"):
        build.require("gui")
    path.write_text(path.read_text().replace("control-type=cli", "control-type=typo"))
    with pytest.raises(ValueError, match="Control type"):
        load_build(path)


def test_manifest_rejects_duplicate_properties(tmp_path):
    path = tmp_path / "build.prop"
    path.write_text("ver=1\nver=2\n")
    with pytest.raises(ValueError, match="Duplicate"):
        load_build(path)
