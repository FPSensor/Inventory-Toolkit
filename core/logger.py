"""Inventory Toolkit logging configuration and structured debug diagnostics.

Debug levels intentionally control *verbosity*, not business behavior:

* level 1: errors only (normal operator mode)
* level 2: operational diagnostics and warnings
* level 3: forensic developer diagnostics

The logger can be reconfigured at runtime by the hidden CLI ``debug`` command.
"""

from __future__ import annotations

import logging
import os
import platform
import sys
import threading
from pathlib import Path
from typing import Any

_LOG_NAME = "InventoryToolkit"
_ROOT = Path(__file__).resolve().parents[1]
_LOG_DIR = _ROOT / "logs"
_SESSION_LOG = _LOG_DIR / "session.log"
DEBUG_LEVEL_ENV = "INVENTORY_TOOLKIT_DEBUG_LEVEL"

_DEBUG_LEVEL = 1
_INITIALIZED = False
_LOCK = threading.RLock()

_CONSOLE_LEVELS = {
    1: logging.ERROR,
    2: logging.INFO,
    3: logging.DEBUG,
}

_SIMPLE_FORMAT = "%(levelname)s - %(message)s"
_FORENSIC_FORMAT = (
    "%(asctime)s.%(msecs)03d | %(levelname)-8s | pid=%(process)d | "
    "%(threadName)s | %(module)s:%(lineno)d | %(message)s"
)
_FILE_FORMAT = (
    "%(asctime)s.%(msecs)03d | %(levelname)-8s | pid=%(process)d | "
    "thread=%(threadName)s | %(name)s | %(module)s:%(lineno)d | %(message)s"
)
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _normalize_debug_level(debug_level: int) -> int:
    try:
        level = int(debug_level)
    except (TypeError, ValueError):
        return 1
    return level if level in _CONSOLE_LEVELS else 1


def get_debug_level() -> int:
    """Return the process-local Inventory Toolkit debug verbosity level."""
    return _DEBUG_LEVEL


def debug_level_from_environment(default: int = 1) -> int:
    """Return the debug level inherited by a newly spawned process.

    Runtime changes made by the CLI are exported through ``DEBUG_LEVEL_ENV`` so
    developer/release subprocesses can reproduce the parent's diagnostic
    verbosity without requiring additional command-line flags.
    """
    return _normalize_debug_level(os.environ.get(DEBUG_LEVEL_ENV, default))


def get_session_log_path() -> Path:
    """Return the absolute path of the current persistent session log."""
    return _SESSION_LOG


def is_forensic_debug() -> bool:
    """Return ``True`` when debug level 3 diagnostics are active."""
    return _DEBUG_LEVEL == 3


def _handler(role: str) -> logging.Handler | None:
    logger = logging.getLogger(_LOG_NAME)
    return next(
        (
            handler
            for handler in logger.handlers
            if getattr(handler, "_inventory_toolkit_role", None) == role
        ),
        None,
    )


def _configure_handlers(
    logger: logging.Logger,
    debug_level: int,
    *,
    reset_session_log: bool,
) -> None:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    console = _handler("console")
    if console is None:
        console = logging.StreamHandler()
        console._inventory_toolkit_role = "console"  # type: ignore[attr-defined]
        logger.addHandler(console)

    file_handler = _handler("file")
    if file_handler is None:
        # Truncate explicitly, then always open in append mode. This matters when
        # developer tools spawn pytest/release subprocesses that also log to the
        # same session file: O_APPEND prevents the parent process from later
        # overwriting child-process records with a stale file offset.
        if reset_session_log:
            _SESSION_LOG.write_text("", encoding="utf-8")
        file_handler = logging.FileHandler(
            _SESSION_LOG,
            mode="a",
            encoding="utf-8",
        )
        file_handler._inventory_toolkit_role = "file"  # type: ignore[attr-defined]
        logger.addHandler(file_handler)

    console.setLevel(_CONSOLE_LEVELS[debug_level])
    file_handler.setLevel(_CONSOLE_LEVELS[debug_level])

    console_formatter = logging.Formatter(
        _FORENSIC_FORMAT if debug_level == 3 else _SIMPLE_FORMAT,
        datefmt=_DATE_FORMAT,
    )
    console.setFormatter(console_formatter)
    file_handler.setFormatter(logging.Formatter(_FILE_FORMAT, datefmt=_DATE_FORMAT))


def setup_logger(
    debug_level: int = 1,
    *,
    reset_session_log: bool = False,
) -> logging.Logger:
    """Configure or reconfigure the shared Inventory Toolkit logger.

    Calling this function repeatedly is safe. Existing handlers are reused so a
    runtime debug-level change does not truncate the current session log.
    """
    global _DEBUG_LEVEL, _INITIALIZED

    normalized = _normalize_debug_level(debug_level)
    with _LOCK:
        logger = logging.getLogger(_LOG_NAME)
        # Keep the logger itself permissive; handlers control runtime verbosity.
        # This makes changing levels in the running CLI immediate and reliable.
        logger.setLevel(logging.DEBUG)
        _configure_handlers(
            logger,
            normalized,
            reset_session_log=reset_session_log,
        )
        _DEBUG_LEVEL = normalized

        if not _INITIALIZED:
            _INITIALIZED = True
            logger.debug(
                "Logger initialized | debug_level=%s | python=%s | executable=%s | "
                "platform=%s | cwd=%s | repository=%s | session_log=%s",
                normalized,
                platform.python_version(),
                sys.executable,
                platform.platform(),
                Path.cwd(),
                _ROOT,
                _SESSION_LOG,
            )
        else:
            logger.debug("Logger verbosity reconfigured | debug_level=%s", normalized)
        return logger


def set_debug_level(
    debug_level: int,
    *,
    reset_session_log: bool = False,
) -> int:
    """Change logger verbosity for the current process and return the active level."""
    previous = _DEBUG_LEVEL
    setup_logger(debug_level, reset_session_log=reset_session_log)
    os.environ[DEBUG_LEVEL_ENV] = str(_DEBUG_LEVEL)
    log.info("Debug verbosity changed: level %s -> level %s", previous, _DEBUG_LEVEL)
    if _DEBUG_LEVEL == 3:
        log.debug(
            "Forensic diagnostics enabled | python=%s | pid=%s | cwd=%s | thread=%s",
            platform.python_version(),
            os.getpid(),
            Path.cwd(),
            threading.current_thread().name,
        )
    return _DEBUG_LEVEL


def _safe_value(value: Any, *, limit: int = 500) -> str:
    try:
        rendered = repr(value)
    except Exception:
        rendered = f"<{type(value).__name__}: unrepresentable>"
    if len(rendered) > limit:
        return rendered[: limit - 3] + "..."
    return rendered


def log_debug_event(event: str, /, **fields: Any) -> None:
    """Emit a compact structured event at forensic debug level.

    This helper is intentionally used for metadata, counts and control-flow
    decisions rather than raw dataset rows. It keeps level-3 logs detailed
    without dumping business spreadsheets into log files.
    """
    if _DEBUG_LEVEL != 3:
        return
    if fields:
        payload = " | ".join(
            f"{key}={_safe_value(value)}" for key, value in sorted(fields.items())
        )
        log.debug("%s | %s", event, payload)
    else:
        log.debug("%s", event)


def log_exception(message: str, *args: Any) -> None:
    """Log an exception with traceback at level 3 and concise output otherwise."""
    if _DEBUG_LEVEL == 3:
        log.exception(message, *args)
    else:
        log.error(message, *args)


log = logging.getLogger(_LOG_NAME)
