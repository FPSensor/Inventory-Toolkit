"""Embedded profile checks and recovery with background I/O and explicit restore."""
import queue
import threading

from core.profile_diagnostics import inspect_configuration
from core.profile_history import checkpoint_info, create_checkpoint, list_checkpoints, restore_checkpoint
from gui.widgets import BaseFrame, BaseScrollable, _btn, _lbl


class ProfileRecoveryPanel(BaseFrame):
    def __init__(self, parent, profile, on_close, on_configure):
        super().__init__(parent)
        self.profile = profile
        self.on_close, self.on_configure = on_close, on_configure
        self._busy = False
        self._closed = False
        self._report = None
        self._points = ()
        self._message = 'Checking configuration...'
        self._confirmation = None
        self._render()
        self._run(self._inspect, self._accept_inspection)

    def _render(self):
        for child in self.winfo_children():
            child.destroy()
        header = BaseFrame(self)
        header.pack(fill='x', padx=20, pady=(16, 8))
        _lbl(header, 'Profile checks and recovery', font=('Arial', 22, 'bold')).pack(anchor='w')
        _lbl(header, 'Check configuration before a run, or return to a saved configuration. Workbooks and remembered paths stay outside recovery.', wraplength=720, justify='left').pack(anchor='w', pady=8)
        actions = BaseFrame(self)
        actions.pack(fill='x', padx=20, pady=4)
        state = 'disabled' if self._busy else 'normal'
        _btn(actions, 'Check again', lambda: self._run(self._inspect, self._accept_inspection), state=state).pack(side='left', padx=(0, 8))
        _btn(actions, 'Save checkpoint', lambda: self._run(lambda: create_checkpoint(self.profile), self._created), state=state).pack(side='left', padx=8)
        _btn(actions, 'Back', self._leave, state=state).pack(side='right')
        self.notice = _lbl(self, self._message, wraplength=740, justify='left')
        self.notice.pack(fill='x', padx=24, pady=10)
        body = BaseScrollable(self)
        body.pack(fill='both', expand=True, padx=16, pady=(0, 16))
        if self._confirmation:
            identifier = self._confirmation
            card = BaseFrame(body); card.pack(fill='x', padx=6, pady=6)
            _lbl(card, 'Restore this checkpoint?', font=('Arial', 16, 'bold')).pack(anchor='w', padx=12, pady=(12, 6))
            _lbl(card, 'Configuration and setup review state will be replaced. The current state is saved first so this restoration can be undone.', wraplength=650, justify='left').pack(anchor='w', padx=12)
            _btn(card, 'Confirm restore', lambda: self._run(lambda: restore_checkpoint(self.profile, identifier), self._restored), variant='danger', state=state).pack(anchor='w', padx=12, pady=8)
            _btn(card, 'Cancel restore', self._cancel_restore, state=state).pack(anchor='w', padx=12, pady=(0, 12))
        if self._report is not None:
            label = 'Configuration checks passed' if self._report.healthy else 'Configuration needs attention'
            _lbl(body, label, font=('Arial', 17, 'bold')).pack(anchor='w', padx=12, pady=(10, 4))
            if not self._report.issues:
                _lbl(body, 'No contradictions detected. Selected workbooks are checked separately.', wraplength=660).pack(anchor='w', padx=12, pady=6)
            for issue in self._report.issues:
                card = BaseFrame(body); card.pack(fill='x', padx=6, pady=5)
                _lbl(card, f'{issue.severity.title()} · {issue.message}', wraplength=650, justify='left').pack(anchor='w', padx=12, pady=10)
                _lbl(card, issue.document, style='Muted.TLabel', wraplength=650).pack(anchor='w', padx=12, pady=(0, 8))
                if issue.module and issue.step:
                    _btn(card, 'Review this setting', lambda module=issue.module, step=issue.step: self._review_setting(module, step), state=state).pack(anchor='w', padx=12, pady=(0, 12))
        _lbl(body, 'Saved configurations', font=('Arial', 17, 'bold')).pack(anchor='w', padx=12, pady=(18, 6))
        if not self._points:
            _lbl(body, 'No checkpoints yet. Setup saves one before changed settings.', wraplength=650).pack(anchor='w', padx=12, pady=6)
        for point in self._points:
            card = BaseFrame(body); card.pack(fill='x', padx=6, pady=5)
            _lbl(card, point['label'], font=('Arial', 14, 'bold'), wraplength=650).pack(anchor='w', padx=12, pady=(10, 4))
            _lbl(card, point['created'], style='Muted.TLabel').pack(anchor='w', padx=12)
            _btn(card, 'Restore...', lambda identifier=point['id']: self._confirm_restore(identifier), state=state).pack(anchor='w', padx=12, pady=10)

    def _inspect(self):
        report = inspect_configuration(self.profile)
        points = []
        for identifier in list_checkpoints(self.profile):
            try:
                points.append(checkpoint_info(self.profile, identifier))
            except (OSError, ValueError):
                points.append({'id': identifier, 'created': 'Unreadable checkpoint', 'label': 'This checkpoint needs review'})
        return report, tuple(points)

    def _accept_inspection(self, result, message=None):
        self._report, self._points = result
        self._message = message or 'Checks finished. This does not review setup pages or inspect workbook contents.'
        self._render()

    def _created(self, _identifier):
        self._run(self._inspect, lambda result: self._accept_inspection(result, 'Checkpoint saved.'))

    def _restored(self, _safety):
        self._confirmation = None
        self._run(self._inspect, lambda result: self._accept_inspection(result, 'Configuration restored; previous state is available in saved configurations.'))

    def _confirm_restore(self, identifier):
        if not self._busy:
            self._confirmation = identifier
            self._render()

    def _cancel_restore(self):
        self._confirmation = None
        self._render()

    def _review_setting(self, module, step):
        if not self._busy:
            self._closed = True
            self.on_configure(module, step)

    def _leave(self):
        if not self._busy:
            self._closed = True
            self.on_close()

    def _run(self, task, completed):
        if self._busy or self._closed:
            return
        self._busy = True
        self._render()
        results = queue.Queue(maxsize=1)
        def worker():
            try:
                results.put((True, task()))
            except Exception as exc:
                results.put((False, exc))
        def poll():
            if self._closed:
                return
            try:
                success, value = results.get_nowait()
            except queue.Empty:
                self.after(50, poll)
                return
            self._busy = False
            if success:
                completed(value)
            else:
                self._message = f'Could not complete the action: {value}'
                self._render()
        try:
            threading.Thread(target=worker, daemon=True).start()
        except Exception as exc:
            self._busy = False
            self._message = f'Could not start the action: {exc}'
            self._render()
            return
        self.after(50, poll)
