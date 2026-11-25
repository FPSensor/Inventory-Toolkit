"""Contracts and steps common to every workflow."""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import Any

from core.input_columns import choose_input_columns
from core.logger import log_debug_event
from core.profile_store import load_last_paths, save_last_paths
from core.system_utils import normalize_xlsx_output_path
from core.workflow_errors import ErrorCode, WorkflowError

# (file, field, configured header, default header) -> use the default this time?
ConfirmColumn = Callable[[str, str, str, str], bool]


@dataclass(frozen=True)
class RunResult:
    """What an interface needs to show after a successful run."""

    output: str
    elapsed: float
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class Job:
    """A verified request. It asks nothing, so it can run on any thread."""

    request: Any
    engine: Callable[..., str]

    def run(self, *, progress=None, stats=None, on_locked=None) -> RunResult:
        warnings, started = [], time.time()
        output = self.engine(progress=progress, stats=stats, warnings=warnings, on_locked=on_locked)
        result = RunResult(output, time.time() - started, tuple(warnings))
        log_debug_event("workflow_complete", output=output, elapsed_seconds=round(result.elapsed, 4))
        return result


def remember(profile: str, module: str, **paths: str) -> None:
    """Keep selections for the next run, even when this one is not finished."""
    save_last_paths(profile, {module: {**load_last_paths(profile).get(module, {}), **paths}})


def require_files(files: Mapping[str, str]) -> None:
    """Report every missing input at once, by its name in the interface."""
    missing = [f"{label}: {path or '(not selected)'}" for label, path in files.items() if not os.path.isfile(path)]
    if missing:
        raise WorkflowError(ErrorCode.INPUT_FILE_MISSING, "Required file not found.\n" + "\n".join(missing))


def choose_columns(path, configured, defaults, confirm_column: ConfirmColumn | None):
    confirm = None if confirm_column is None else lambda *question: confirm_column(path, *question)
    return choose_input_columns(path, configured, defaults, confirm)


def settle_output(request, module: str, default: str, notify=None):
    """Return the request with its final output name, remembered for the next run."""
    request = replace(request, output=normalize_xlsx_output_path(request.output.strip() or default, notify=notify))
    remember(request.profile, module, out=request.output)
    return request
