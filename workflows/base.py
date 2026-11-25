"""Contracts common to every workflow."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from core.workflow_errors import ErrorCode, WorkflowError

# (file, field, configured header, default header) -> use the default this time?
ConfirmColumn = Callable[[str, str, str, str], bool]


@dataclass(frozen=True)
class RunResult:
    """What an interface needs to show after a successful run."""

    output: str
    elapsed: float
    warnings: tuple[str, ...] = ()


def require_files(files: Mapping[str, str]) -> None:
    """Report every missing input at once, by its name in the interface."""
    missing = [f"{label}: {path or '(not selected)'}" for label, path in files.items() if not os.path.isfile(path)]
    if missing:
        raise WorkflowError(ErrorCode.INPUT_FILE_MISSING, "Required file not found.\n" + "\n".join(missing))


def require_output(output, elapsed: float, warnings) -> RunResult:
    if not output:
        raise WorkflowError(
            ErrorCode.REPORT_NOT_CREATED,
            "The operation finished without producing an output file. "
            "Check logs/session.log for the validation error.",
        )
    return RunResult(output, elapsed, tuple(warnings))
