from types import SimpleNamespace

from cli.progress import show_progress, show_stats
from core.progress import ProgressEvent, StatsEvent
from gui.app import InventoryToolkitGUI


def test_cli_prints_stats_after_completion_outside_percentage_lines(capsys):
    show_progress(ProgressEvent(3, 3, "Report saved."))
    show_stats(StatsEvent(("Differences: 2", "Shortages: 1")))

    lines = capsys.readouterr().out.splitlines()
    assert lines.index("  [3/3 | 100%] Report saved.") < lines.index("Stats:")
    assert "  Differences: 2" in lines
    assert "  Shortages: 1" in lines


def test_gui_appends_stats_without_overwriting_progress():
    class Activity:
        def __init__(self):
            self.content = ""

        def configure(self, **_kwargs):
            pass

        def insert(self, _position, value):
            self.content += value

        def see(self, _position):
            pass

    view = SimpleNamespace(_activity=Activity())
    rendered = InventoryToolkitGUI._show_stats(view, StatsEvent(("Families: 3",)))

    assert rendered == "Stats:\n  Families: 3"
    assert rendered in view._activity.content
