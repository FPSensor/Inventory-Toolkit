import json
import logging

from core.compatibility import (
    configure_compatibility_diagnostics,
    reset_compatibility_diagnostics,
)
from core.configuration_manager import ConfigurationManager


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_legacy_api_warning_is_debug_only_and_emitted_once(tmp_path, monkeypatch, caplog):
    monkeypatch.chdir(tmp_path)
    config = ConfigurationManager("test")

    reset_compatibility_diagnostics()
    with caplog.at_level(logging.WARNING, logger="InventoryToolkit"):
        config.get_config("familias")
        assert "Deprecated configuration compatibility API" not in caplog.text

        configure_compatibility_diagnostics(True)
        config.get_config("familias")
        config.get_config("familias")

    assert caplog.text.count("Deprecated configuration compatibility API") == 1
    assert "module-oriented English API" in caplog.text
    reset_compatibility_diagnostics()


def test_legacy_storage_warning_points_to_migration_action(tmp_path, monkeypatch, caplog):
    base = tmp_path / "profiles" / "old" / "configs"
    _write_json(base / "general" / "settings.json", {"columna_articulo": "SKU"})

    monkeypatch.chdir(tmp_path)
    reset_compatibility_diagnostics()
    configure_compatibility_diagnostics(True)

    with caplog.at_level(logging.WARNING, logger="InventoryToolkit"):
        ConfigurationManager("old")

    assert "Deprecated legacy configuration storage detected" in caplog.text
    assert "Migrate/archive legacy config" in caplog.text
    reset_compatibility_diagnostics()
