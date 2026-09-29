"""Compact progress output for interactive workflows."""

from core.progress import ProgressEvent


def show_progress(event: ProgressEvent) -> None:
    print(f"  [{event.completed}/{event.total} | {event.fraction:.0%}] {event.message}")
