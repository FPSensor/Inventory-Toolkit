"""Human-readable workflow updates for CLI and GUI consumers."""

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class ProgressEvent:
    completed: int
    total: int
    message: str
    stage_fraction: float = 0.0

    @property
    def fraction(self) -> float:
        return (self.completed + self.stage_fraction) / self.total


ProgressCallback = Callable[[ProgressEvent], None]


def report_progress(
    callback: Optional[ProgressCallback],
    completed: int,
    total: int,
    message: str,
    *,
    stage_fraction: float = 0.0,
) -> None:
    if callback is not None:
        callback(ProgressEvent(completed, total, message, stage_fraction))
