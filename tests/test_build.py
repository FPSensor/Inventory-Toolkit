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


def test_debug_is_optional_and_release_archives_exclude_development(monkeypatch):
    from dataclasses import replace
    from core import optional_debug
    from tools.BuildDistribution import distribution_files, ROOT
    from core.build import BUILD

    release = replace(BUILD, type="release", control_type="cli", default_control="cli")
    monkeypatch.setattr(optional_debug, "BUILD", release)
    monkeypatch.setattr(optional_debug.util, "find_spec", lambda _name: (_ for _ in ()).throw(AssertionError("must not probe debug in release")))
    assert not optional_debug.debug_available()
    assert not optional_debug.open_debug_console()
    paths = [path.relative_to(ROOT) for path in distribution_files(release)]
    assert not any(path.parts[0] in {"gui", "tests", "tools", "debug_tools"} for path in paths)
    assert Path("cli/menu.py") in paths and Path("build.prop") in paths
    monkeypatch.setattr(optional_debug, "BUILD", BUILD)
    monkeypatch.setattr(optional_debug.util, "find_spec", lambda _name: None)
    assert not optional_debug.debug_available()


@pytest.mark.parametrize('interface', ['cli', 'gui', 'both'])
def test_release_source_tree_imports_without_excluded_packages(tmp_path, interface):
    from dataclasses import replace
    import shutil
    import subprocess
    import sys
    from tools.BuildDistribution import distribution_files, ROOT
    from core.build import BUILD
    default = 'gui' if interface == 'gui' else 'cli'
    release = replace(BUILD, type='release', control_type=interface, default_control=default)
    for source in distribution_files(release):
        destination = tmp_path / source.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    manifest = (tmp_path / 'build.prop').read_text()
    manifest = manifest.replace('type = debug', 'type = release').replace('control-type = both', f'control-type = {interface}').replace('default-control = cli', f'default-control = {default}')
    (tmp_path / 'build.prop').write_text(manifest)
    assert not (tmp_path / 'debug_tools').exists()
    assert not (tmp_path / 'tests').exists()
    if interface != 'both':
        assert not (tmp_path / ('gui' if interface == 'cli' else 'cli')).exists()
    imports = 'import cli.menu' if interface == 'cli' else 'import gui.app'
    code = imports + '; from core.optional_debug import debug_available; assert not debug_available()'
    result = subprocess.run([sys.executable, '-c', code], cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    result = subprocess.run([sys.executable, '-m', 'inventory_toolkit', '--version'], cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0 and result.stdout.strip() == BUILD.version
