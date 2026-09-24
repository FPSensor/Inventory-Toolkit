import logging
import os

from core.logger import (
    DEBUG_LEVEL_ENV,
    debug_level_from_environment,
    get_debug_level,
    log_debug_event,
    set_debug_level,
    setup_logger,
)


def _role_handler(logger, role):
    return next(
        handler
        for handler in logger.handlers
        if getattr(handler, "_inventory_toolkit_role", None) == role
    )


def test_logger_can_change_debug_level_at_runtime():
    logger = setup_logger(1)
    console = _role_handler(logger, "console")
    assert console.level == logging.ERROR
    assert get_debug_level() == 1

    set_debug_level(3)
    assert console.level == logging.DEBUG
    assert get_debug_level() == 3

    set_debug_level(2)
    assert console.level == logging.INFO
    assert get_debug_level() == 2

    set_debug_level(1)
    assert console.level == logging.ERROR


def test_forensic_event_is_safe_to_call_at_any_level():
    set_debug_level(1)
    log_debug_event("unit_test_event", rows=10, columns=["A", "B"])
    set_debug_level(3)
    log_debug_event("unit_test_event", rows=10, columns=["A", "B"])
    set_debug_level(1)


def test_runtime_debug_level_is_exported_for_child_processes(monkeypatch):
    monkeypatch.delenv(DEBUG_LEVEL_ENV, raising=False)

    for level in (1, 2, 3):
        set_debug_level(level)
        assert os.environ[DEBUG_LEVEL_ENV] == str(level)
        assert debug_level_from_environment() == level

    set_debug_level(1)


def test_invalid_inherited_debug_level_falls_back_to_operator_mode(monkeypatch):
    monkeypatch.setenv(DEBUG_LEVEL_ENV, "definitely-not-a-level")
    assert debug_level_from_environment() == 1
