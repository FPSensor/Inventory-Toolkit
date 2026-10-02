"""Exercise GUI task lifecycle without requiring a display server."""

from threading import Event
from types import SimpleNamespace

import pytest

from core.progress import ProgressEvent, StatsEvent
from gui import app


class Variable:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class Widget:
    def __init__(self, state=None, children=()):
        self.state = state
        self.children = list(children)
        self.content = ""
        self.value = 0

    def cget(self, name):
        if name != "state" or self.state is None:
            raise app.tk.TclError("Unsupported option")
        return self.state

    def configure(self, **options):
        if "state" in options:
            self.state = options["state"]

    def winfo_children(self):
        return self.children

    def winfo_exists(self):
        return True

    def delete(self, *_):
        self.content = ""

    def insert(self, _index, value):
        self.content += value

    def see(self, *_):
        pass

    def set(self, value):
        self.value = value

    def __setitem__(self, _key, value):
        self.value = value


class View:
    _set_busy = app.InventoryToolkitGUI._set_busy
    _require_idle = app.InventoryToolkitGUI._require_idle
    _run_async = app.InventoryToolkitGUI._run_async
    _show_progress = app.InventoryToolkitGUI._show_progress
    _show_stats = app.InventoryToolkitGUI._show_stats
    _finish_progress = app.InventoryToolkitGUI._finish_progress
    _on_profile_changed = app.InventoryToolkitGUI._on_profile_changed
    _request_close = app.InventoryToolkitGUI._request_close

    def __init__(self):
        self._busy = False
        self._running_profile = None
        self._locked_controls = []
        self.active_profile = Variable("test")
        self.action = Widget("normal")
        self.profile_menu = Widget("readonly")
        self.option = Widget("disabled")
        self._top_bar = Widget(children=[self.action, self.profile_menu])
        self.tab_cc = Widget(children=[self.option])
        self.tab_stock = Widget()
        self.tab_yoy = Widget()
        self._activity = Widget("disabled")
        self._progress = Widget()
        self.pending = []
        self.destroyed = False
        self.status = ""

    def after(self, _delay, callback):
        self.pending.append(callback)

    def winfo_children(self):
        return []

    def _set_status(self, message):
        self.status = message

    def destroy(self):
        self.destroyed = True


@pytest.fixture
def dialogs(monkeypatch):
    calls = []
    monkeypatch.setattr(app.messagebox, "showinfo", lambda *args, **kwargs: calls.append(("info", args)))
    monkeypatch.setattr(app.messagebox, "showerror", lambda *args, **kwargs: calls.append(("error", args)))
    return calls


def test_busy_restores_readonly_and_disabled_states_and_freezes_profile(dialogs):
    view = View()
    view._set_busy(True)
    assert view.action.state == view.profile_menu.state == "disabled"
    view.active_profile.set("other")
    view._on_profile_changed()
    assert view.active_profile.get() == "test"
    view._request_close()
    assert not view.destroyed
    view._set_busy(False)
    assert view.action.state == "normal"
    assert view.profile_menu.state == "readonly"
    assert view.option.state == "disabled"
    view._request_close()
    assert view.destroyed


@pytest.mark.parametrize("ctk", [False, True])
@pytest.mark.parametrize("failure", [False, True])
def test_run_blocks_overlap_and_restores_controls_after_completion(monkeypatch, dialogs, ctk, failure):
    monkeypatch.setattr(app, "USE_CTK", ctk)
    release = Event()
    finished = Event()
    started = Event()
    view = View()

    def work(progress, stats):
        started.set()
        assert release.wait(5)
        progress(ProgressEvent(3, 3, "Saved."))
        if failure:
            raise RuntimeError("Cannot save output")
        stats(StatsEvent(("Rows: 2",)))
        return "report.xlsx"

    real_thread = app.threading.Thread
    threads = []

    def tracked_thread(*args, **kwargs):
        target = kwargs["target"]

        def wrapped():
            try:
                target()
            finally:
                finished.set()

        kwargs["target"] = wrapped
        thread = real_thread(*args, **kwargs)
        threads.append(thread)
        return thread

    monkeypatch.setattr(app.threading, "Thread", tracked_thread)
    view._run_async(work, "Completed")
    try:
        assert started.wait(5)
        assert view._busy
        view._run_async(lambda *_: pytest.fail("Overlapping worker started"), "Other")
        assert len(threads) == 1
    finally:
        release.set()
        assert finished.wait(5)
        threads[0].join()
    view.pending.pop(0)()
    assert not view._busy
    assert view.action.state == "normal"
    assert view.option.state == "disabled"
    if failure:
        assert dialogs[-1][0] == "error"
        assert "Cannot save output" in view.status
    else:
        assert "Stats:\n  Rows: 2" in view._activity.content
        assert "Stats:\n  Rows: 2" in dialogs[-1][1][1]
        assert view._progress.value == (1 if ctk else 100)


def test_worker_start_failure_unlocks_controls(monkeypatch, dialogs):
    view = View()

    def fail_start():
        raise RuntimeError("Cannot start worker")

    monkeypatch.setattr(app.threading, "Thread", lambda **_: SimpleNamespace(start=fail_start))
    view._run_async(lambda *_: "report.xlsx", "Completed")
    assert not view._busy
    assert view.profile_menu.state == "readonly"
    assert dialogs[-1][0] == "error"


def test_open_configuration_window_prevents_start(monkeypatch, dialogs):
    view = View()
    window_type = type("ConfigWindow", (), {})
    monkeypatch.setattr(app.tk, "Toplevel", window_type)
    view.winfo_children = lambda: [window_type()]
    view._run_async(lambda *_: pytest.fail("Worker started with an editor open"), "Completed")
    assert not view._busy
    assert not view.pending
    assert dialogs[-1][1][0] == "Configuration window open"


def test_final_stats_are_drained_again_after_completion_arrives(monkeypatch, dialogs):
    real_queue = app.queue.Queue
    made = []

    class DelayedStats(real_queue):
        def __init__(self):
            super().__init__()
            self.first_read = True

        def get_nowait(self):
            if self.first_read:
                self.first_read = False
                raise app.queue.Empty
            return super().get_nowait()

    def make_queue(*args, **kwargs):
        result = DelayedStats() if len(made) == 2 else real_queue(*args, **kwargs)
        made.append(result)
        return result

    monkeypatch.setattr(app.queue, "Queue", make_queue)
    monkeypatch.setattr(app.threading, "Thread", lambda **kwargs: SimpleNamespace(start=kwargs["target"]))
    view = View()

    def work(_progress, stats):
        stats(StatsEvent(("Rows: 2",)))
        return "report.xlsx"

    view._run_async(work, "Completed")
    view.pending.pop(0)()
    assert "Stats:\n  Rows: 2" in dialogs[-1][1][1]
    assert not view._busy
