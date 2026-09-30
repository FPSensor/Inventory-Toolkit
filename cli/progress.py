"""Compact progress output for interactive workflows."""

from core.progress import ProgressEvent, StatsEvent


def show_progress(event: ProgressEvent) -> None:
    print(f"  [{event.completed}/{event.total} | {event.fraction:.0%}] {event.message}")


def show_stats(event: StatsEvent) -> None:
    print(f"\n{event.render()}\n")
