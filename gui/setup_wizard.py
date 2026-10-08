"""Embedded, resumable module setup with human labels and Excel previews."""
import queue
import threading
import tkinter as tk

import pandas as pd
from tkinter import filedialog

from core.setup_catalog import MODULE_LABELS, get_value
from core.setup_service import SetupSession, SetupState
from core.workflow_errors import WorkflowError
from gui.widgets import BaseFrame, BaseScrollable, BaseTextbox, USE_CTK, ctk, ttk, _btn, _lbl, _entry


def table_value(kind, rows):
    """Convert inline rows to typed configuration, rejecting ambiguous keys."""
    if kind == 'summaries':
        result = []
        for name, entities, titles in rows:
            if not any((name.strip(), entities.strip(), titles.strip())):
                continue
            if not name.strip():
                raise ValueError('Every summary needs a sheet name.')
            result.append({'sheet_name': name.strip(), 'entities': split_members(entities), 'titles': split_members(titles)})
        if len({item['sheet_name'] for item in result}) != len(result):
            raise ValueError('Summary sheet names must be unique.')
        return result
    result = {}
    for key, value in rows:
        key, value = key.strip(), value.strip()
        if not key and not value:
            continue
        if not key or not value:
            raise ValueError('Each row needs both a name and a value. Remove unused rows.')
        if key in result:
            raise ValueError(f'The name {key!r} appears more than once.')
        result[key] = split_members(value) if kind in {'rules', 'groups'} else value
    return result


def family_rule_warnings(rules):
    owners = {}
    for family, prefixes in rules.items():
        for prefix in prefixes:
            owners.setdefault(prefix, set()).add(family)
    return [f"Prefix {prefix!r} belongs to multiple families: {', '.join(sorted(families))}. Review the competing rules."
            for prefix, families in owners.items() if len(families) > 1]


def split_members(value):
    return list(dict.fromkeys(item.strip() for item in value.split(',') if item.strip()))


class SetupWizard(BaseFrame):
    def __init__(self, parent, profile, module, on_exit, step_id=None):
        super().__init__(parent)
        self.session = SetupSession(profile, module)
        self.on_exit = on_exit
        self.index = next((i for i, step in enumerate(self.session.steps) if step.id == (step_id or self.session.first_pending())), 0)
        self._closed = False
        self._loading = False
        self._samples = {}
        self._getters = {}
        self._render()

    def _render(self, draft=None):
        for widget in self.winfo_children():
            widget.destroy()
        step = self.session.steps[self.index]
        self._getters = {}
        _lbl(self, text=f'{MODULE_LABELS[self.session.module]} setup | Step {self.index + 1} of {len(self.session.steps)}', font=('Arial', 15, 'bold')).pack(anchor='w', padx=20, pady=(16, 6))
        _lbl(self, text=step.title, font=('Arial', 20, 'bold')).pack(anchor='w', padx=20)
        if step.shared:
            _lbl(self, text='Shared setting: changes affect other modules in this profile.', wraplength=650).pack(anchor='w', padx=20, pady=4)
        self.notice = _lbl(self, text='Saved pages remain available when you leave. Review defaults before continuing.', wraplength=650, justify='left')
        self.notice.pack(fill='x', padx=20, pady=6)
        sample_bar = BaseFrame(self)
        sample_bar.pack(fill='x', padx=20, pady=6)
        self._sample_button = _btn(sample_bar, 'Choose sample Excel', self._load_sample)
        self._sample_button.pack(side='left', padx=4)
        _lbl(sample_bar, text='Optional: read headers and up to five example rows.').pack(side='left', padx=8)
        self.content = BaseScrollable(self)
        self.content.pack(fill='both', expand=True, padx=20, pady=6)
        data = self.session.data(step)
        for field in step.fields:
            self._render_field(field, (draft or {}).get(".".join(field.path), get_value(data, field.path)))
        footer = BaseFrame(self)
        footer.pack(fill='x', padx=20, pady=12)
        self._back_button = _btn(footer, 'Back', self._back)
        self._back_button.pack(side='left', padx=4)
        if self.index == 0:
            self._back_button.configure(state='disabled')
        _btn(footer, 'Leave setup', self._leave).pack(side='left', padx=4)
        self._next_button = _btn(footer, 'Save & finish' if self.index == len(self.session.steps) - 1 else 'Save & next', self._next)
        self._next_button.pack(side='right', padx=4)

    def _render_field(self, field, value):
        block = BaseFrame(self.content)
        block.pack(fill='x', pady=8, padx=4)
        _lbl(block, text=field.label, font=('Arial', 13, 'bold')).pack(anchor='w', padx=10, pady=(8, 2))
        help_label = _lbl(block, text=field.help, wraplength=600, justify='left')
        help_label.pack(fill='x', padx=10, pady=(0, 6))
        block.bind('<Configure>', lambda event: help_label.configure(wraplength=max(180, event.width - 30)))
        key = '.'.join(field.path)
        if field.kind == 'bool':
            variable = tk.BooleanVar(value=value)
            cls = ctk.CTkCheckBox if USE_CTK else ttk.Checkbutton
            cls(block, text='Enabled', variable=variable).pack(anchor='w', padx=10, pady=8)
            self._getters[key] = variable.get
        elif field.kind == 'list':
            box = BaseTextbox(block, height=85 if USE_CTK else 4)
            box.pack(fill='x', padx=10, pady=8)
            box.insert('1.0', '\n'.join(value))
            self._getters[key] = lambda: list(dict.fromkeys(line.strip() for line in box.get('1.0', 'end').splitlines() if line.strip()))
        elif field.kind in {'rules', 'groups', 'mapping', 'summaries'}:
            self._render_table(block, field.kind, value, key)
        else:
            tokens = {"First word only": "first_token", "Full identifier": "whole"}
            display = next((label for label, stored in tokens.items() if stored == value), value) if field.kind == "token" else value
            variable = tk.StringVar(value=display)
            values = list(tokens) if field.kind == "token" else list(self._samples)
            if field.kind in {'column', 'token'}:
                combo = ctk.CTkComboBox(block, values=values or [''], variable=variable) if USE_CTK else ttk.Combobox(block, values=values, textvariable=variable)
                if field.kind == 'token':
                    combo.configure(state='readonly')
                combo.pack(fill='x', padx=10, pady=8)
            else:
                _entry(block, textvariable=variable).pack(fill='x', padx=10, pady=8)
            self._getters[key] = (lambda: tokens[variable.get()]) if field.kind == "token" else (lambda: variable.get().strip())
            if field.kind == 'column':
                preview = _lbl(block, text='', wraplength=600, justify='left')
                preview.pack(fill='x', padx=10, pady=(0, 8))
                def update(*_args):
                    sample = self._samples.get(variable.get())
                    preview.configure(text=('Examples: ' + ' | '.join(sample)) if sample else 'No sample values for this header. You can type a header manually.')
                variable.trace_add('write', update)
                update()

    def _render_table(self, parent, kind, value, key):
        rows = []
        headings = ('Sheet name', 'Stores (comma separated)', 'Display titles (comma separated)') if kind == 'summaries' else ('Name / source', 'Prefixes / members (comma separated)' if kind in {'rules', 'groups'} else 'Value / target')
        _lbl(parent, text=' | '.join(headings), wraplength=600).pack(anchor='w', padx=10)
        warning = _lbl(parent, text="", wraplength=600, justify="left")
        warning.pack(fill="x", padx=10)
        def refresh_warning(*_args):
            if kind != "rules":
                return
            try:
                rules = table_value(kind, [[variable.get() for variable in variables] for _row, variables in rows])
                warning.configure(text="\n".join(family_rule_warnings(rules)))
            except ValueError:
                warning.configure(text="Finish or remove the incomplete row before saving.")
        holder = BaseFrame(parent)
        holder.pack(fill='x', padx=10, pady=4)
        def add(values=None):
            row = BaseFrame(holder)
            row.pack(fill='x', pady=3)
            variables = [tk.StringVar(value=item) for item in (values or [''] * len(headings))]
            for variable in variables:
                _entry(row, textvariable=variable, width=130 if USE_CTK else None).pack(side='left', fill='x', expand=True, padx=2)
            item = (row, variables)
            rows.append(item)
            def remove():
                rows.remove(item)
                row.destroy()
                refresh_warning()
            for variable in variables:
                variable.trace_add("write", refresh_warning)
            refresh_warning()
            _btn(row, 'Remove', remove, width=75 if USE_CTK else None).pack(side='right', padx=2)
        if kind == 'summaries':
            for item in value:
                add([item['sheet_name'], ', '.join(item.get('entities', [])), ', '.join(item.get('titles', []))])
        else:
            for name, item in value.items():
                add([name, ', '.join(item) if isinstance(item, list) else item])
        _btn(parent, 'Add row', add).pack(anchor='w', padx=10, pady=6)
        self._getters[key] = lambda: table_value(kind, [[variable.get() for variable in variables] for _row, variables in rows])

    def _save(self):
        if self._loading:
            return False
        try:
            values = {key: getter() for key, getter in self._getters.items()}
            self.session.save_step(self.session.steps[self.index].id, values)
        except (ValueError, OSError) as exc:
            self.notice.configure(text=str(exc))
            return False
        return True

    def _next(self):
        if not self._save():
            return
        if self.index < len(self.session.steps) - 1:
            self.index += 1
            self._render()
        else:
            try:
                self.session.validate_required()
            except WorkflowError as exc:
                self.index = next((i for i, step in enumerate(self.session.steps) if step.id == exc.step), self.index)
                self._render()
                self.notice.configure(text=str(exc))
                return
            self._closed = True
            self.on_exit(f'{MODULE_LABELS[self.session.module]} setup complete. Select Run when you are ready.')

    def _back(self):
        if self.index > 0 and self._save():
            self.index -= 1
            self._render()

    def _leave(self):
        if self._loading:
            self.notice.configure(text='Wait for the sample to finish reading before leaving.')
            return
        # Only committed pages survive; the current draft is deliberately not reviewed.
        self._closed = True
        self.on_exit('Setup paused. Saved pages are retained; unsaved changes on this page were discarded.')

    def _load_sample(self):
        if self._loading:
            return
        path = filedialog.askopenfilename(parent=self, filetypes=[('Excel workbooks', '*.xlsx *.xls')])
        if not path:
            return
        result = queue.Queue()
        self._loading = True
        self._sample_button.configure(state='disabled')
        self._next_button.configure(state='disabled')
        self._back_button.configure(state='disabled')
        self.notice.configure(text='Reading sample headers and examples...')
        def worker():
            try:
                frame = pd.read_excel(path, nrows=5, dtype=str)
                result.put((True, {str(column): [str(item) for item in frame[column].dropna().head(5)] for column in frame.columns}))
            except Exception as exc:
                result.put((False, str(exc)))
        def poll():
            if self._closed:
                return
            try:
                ok, payload = result.get_nowait()
            except queue.Empty:
                self.after(80, poll)
                return
            self._loading = False
            # Keep typed drafts while updating available sample headers.
            try:
                draft = {key: getter() for key, getter in self._getters.items()}
            except ValueError as exc:
                self._render_controls_after_sample()
                self.notice.configure(text=f'Fix the unfinished table row before loading another sample: {exc}')
                return
            if ok:
                self._samples = payload
                self._render(draft)
                self.notice.configure(text=f'Read {len(payload)} columns. Sample values stay in this session only.')
            else:
                self._sample_button.configure(state='normal')
                self._next_button.configure(state='normal')
                self._back_button.configure(state='normal' if self.index else 'disabled')
                self.notice.configure(text=f'Could not read sample: {payload}')
        try:
            threading.Thread(target=worker, daemon=True).start()
        except RuntimeError as exc:
            self._loading = False
            self.notice.configure(text=str(exc))
            self._sample_button.configure(state='normal')
            self._next_button.configure(state='normal')
            self._back_button.configure(state='normal' if self.index else 'disabled')
            return
        self.after(80, poll)

    def _render_controls_after_sample(self):
        self._sample_button.configure(state='normal')
        self._next_button.configure(state='normal')
        self._back_button.configure(state='normal' if self.index else 'disabled')
