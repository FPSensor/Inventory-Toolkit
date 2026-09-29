"""Human-readable workflow updates for CLI and GUI consumers."""

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class ProgressEvent:
    completed: int
    total: int
    message: str

    @property
    def fraction(self) -> float:
        return self.completed / self.total


ProgressCallback = Callable[[ProgressEvent], None]


def report_progress(callback: Optional[ProgressCallback], completed: int, total: int, message: str) -> None:
    if callback is not None:
        callback(ProgressEvent(completed, total, message))
