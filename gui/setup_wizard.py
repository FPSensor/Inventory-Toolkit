"""Embedded, resumable module setup with human labels and Excel previews."""
import queue
import threading
import tkinter as tk

import pandas as pd
from tkinter import filedialog

from core.setup_catalog import MODULE_LABELS, STEPS, get_value
from core.column_assist import advise_columns
from core.profile_store import save_last_paths
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
    def __init__(self, parent, profile, module, on_exit, step_id=None, *, edit_mode=False, single_page=False):
        super().__init__(parent)
        self.session = SetupSession(profile, module, include_advanced=edit_mode or bool(step_id and any(step.id == step_id and step.advanced for step in STEPS[module])))
        self.on_exit = on_exit
        self.single_page = single_page
        self.index = next((i for i, step in enumerate(self.session.steps) if step.id == (step_id or self.session.first_pending())), 0)
        self._closed = False
        self._loading = False
        self._samples = {}
        self._samples_by_step = {}
        self._getters = {}
        self._column_variables = {}
        self._render()

    def _render(self, draft=None):
        for widget in self.winfo_children():
            widget.destroy()
        step = self.session.steps[self.index]
        self._getters, self._column_variables = {}, {}
        self._samples = self._samples_by_step.get(step.sample or step.id, {})
        rail = BaseFrame(self, width=190)
        rail.pack(side='left', fill='y', padx=(8, 12), pady=8)
        rail.pack_propagate(False)
        _lbl(rail, text='SETUP' if not self.single_page else 'SETTINGS', style='Muted.TLabel', font=('Arial', 10, 'bold')).pack(anchor='w', padx=12, pady=(14, 4))
        _lbl(rail, text=MODULE_LABELS[self.session.module], font=('Arial', 14, 'bold'), wraplength=165, justify='left').pack(anchor='w', padx=12, pady=(0, 12))
        navigation = BaseScrollable(rail)
        navigation.pack(fill='both', expand=True)
        reviews = self.session.effective_reviews() or {}
        for index, item in enumerate(self.session.steps):
            done = reviews.get(item.id) == self.session.fingerprint(item)
            title = item.title if len(item.title) <= 21 else item.title[:20] + '…'
            prefix = '✓' if done else str(index + 1)
            _btn(navigation, f'{prefix}  {title}', lambda step_id=item.id: self._jump(step_id),
                variant='secondary' if index == self.index else 'ghost', anchor='w').pack(fill='x', padx=6, pady=3)
        body = BaseFrame(self)
        body.pack(side='left', fill='both', expand=True, padx=(0, 8), pady=8)
        _lbl(body, text=f'Step {self.index + 1} of {len(self.session.steps)}', style='Muted.TLabel').pack(anchor='w', padx=20, pady=(16, 4))
        _lbl(body, text=step.title, font=('Arial', 22, 'bold'), wraplength=600, justify='left').pack(anchor='w', padx=20, pady=(0, 4))
        if USE_CTK:
            progress = ctk.CTkProgressBar(body, height=4)
            progress.set(self.index / max(1, len(self.session.steps)))
        else:
            progress = ttk.Progressbar(body, maximum=len(self.session.steps), value=self.index)
        progress.pack(fill='x', padx=20, pady=8)
        self.notice = _lbl(body, text=('Shared settings affect this profile’s other workflows. ' if step.shared else '') +
            'Saved pages are retained. Review this page before continuing.', wraplength=600, justify='left', style='Muted.TLabel')
        self.notice.pack(fill='x', padx=20, pady=6)
        sample_bar = BaseFrame(body)
        sample_bar.pack(fill='x', padx=16, pady=4)
        self._sample_button = _btn(sample_bar, 'Choose your Excel file', self._load_sample)
        if any(field.kind == 'column' for field in step.fields) or step.sample:
            self._sample_button.pack(side='left', padx=4)
            if self._samples:
                _btn(sample_bar, 'Use matching headers', self._apply_suggestions).pack(side='left', padx=4)
        if not self.single_page:
            advanced = tk.BooleanVar(value=self.session.include_advanced)
            cls = ctk.CTkCheckBox if USE_CTK else ttk.Checkbutton
            cls(body, text='Show additional settings', variable=advanced,
                command=lambda: self._toggle_advanced(advanced.get())).pack(anchor='w', padx=20, pady=6)
        self.content = BaseScrollable(body)
        self.content.pack(fill='both', expand=True, padx=16, pady=6)
        data = self.session.data(step)
        self._initial_values = {'.'.join(field.path): get_value(data, field.path) for field in step.fields}
        for field in step.fields:
            self._render_field(field, (draft or {}).get('.'.join(field.path), get_value(data, field.path)))
        self._footer = BaseFrame(body)
        self._footer.pack(fill='x', padx=16, pady=12)
        self._back_button = _btn(self._footer, 'Back', self._back)
        self._back_button.pack(side='left', padx=4)
        if self.index == 0:
            self._back_button.configure(state='disabled')
        _btn(self._footer, 'Close settings' if self.single_page else 'Pause setup', self._leave, variant='ghost').pack(side='left', padx=4)
        label = 'Save changes' if self.single_page else ('Review setup' if self.index == len(self.session.steps) - 1 else 'Save & next')
        self._next_button = _btn(self._footer, label, self._next, variant='primary')
        self._next_button.pack(side='right', padx=4)

    def _jump(self, step_id):
        if self._save():
            self.index = next((i for i, step in enumerate(self.session.steps) if step.id == step_id), min(self.index, len(self.session.steps) - 1))
            self._render()

    def _toggle_advanced(self, enabled):
        step_id = self.session.steps[self.index].id
        if not self._save():
            return
        self.session.include_advanced = enabled
        self.index = next((i for i, step in enumerate(self.session.steps) if step.id == step_id), 0)
        self._render()

    def _render_review(self):
        for child in self.winfo_children():
            child.destroy()
        _lbl(self, text='Review your setup', font=('Arial', 24, 'bold')).pack(anchor='w', padx=24, pady=(24, 8))
        _lbl(self, text='Your settings are saved. Finishing returns to the workflow; Run remains a separate action.', wraplength=700, justify='left', style='Muted.TLabel').pack(anchor='w', padx=24, pady=(0, 12))
        content = BaseScrollable(self)
        content.pack(fill='both', expand=True, padx=20, pady=8)
        for line in self.session.review_summary():
            _lbl(content, text=line, wraplength=650, justify='left').pack(anchor='w', padx=12, pady=5)
        footer = BaseFrame(self)
        footer.pack(fill='x', padx=20, pady=16)
        _btn(footer, 'Back to settings', self._render).pack(side='left')
        _btn(footer, 'Finish setup', self._complete, variant='primary').pack(side='right')

    def _complete(self):
        self._closed = True
        self.on_exit(f'{MODULE_LABELS[self.session.module]} setup complete. Choose files and Run when ready.')

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
        elif field.kind == 'metrics':
            variables = {name: tk.BooleanVar(value=name in value) for name in ('units', 'sales')}
            for name, title in [('units', 'Quantities'), ('sales', 'Revenue')]:
                cls = ctk.CTkCheckBox if USE_CTK else ttk.Checkbutton
                cls(block, text=title, variable=variables[name]).pack(anchor='w', padx=10, pady=5)
            self._getters[key] = lambda: [name for name, variable in variables.items() if variable.get()]
        elif field.kind == 'list':
            box = BaseTextbox(block, height=85 if USE_CTK else 4)
            box.pack(fill='x', padx=10, pady=8)
            box.insert('1.0', '\n'.join(value))
            self._getters[key] = lambda: list(dict.fromkeys(line.strip() for line in box.get('1.0', 'end').splitlines() if line.strip()))
        elif field.kind in {'rules', 'groups', 'mapping', 'summaries'}:
            self._render_table(block, field.kind, value, key)
        else:
            tokens = dict(field.choices) if field.kind == "choice" else {"First word only": "first_token", "Full identifier": "whole"}
            display = next((label for label, stored in tokens.items() if stored == value), value) if field.kind in {"token", "choice"} else value
            variable = tk.StringVar(value=display)
            values = list(tokens) if field.kind in {"token", "choice"} else list(self._samples)
            if field.kind in {'column', 'token', 'choice'}:
                combo = ctk.CTkComboBox(block, values=values or [''], variable=variable) if USE_CTK else ttk.Combobox(block, values=values, textvariable=variable)
                if field.kind == 'token':
                    combo.configure(state='readonly')
                combo.pack(fill='x', padx=10, pady=8)
            else:
                _entry(block, textvariable=variable).pack(fill='x', padx=10, pady=8)
            self._getters[key] = (lambda: tokens[variable.get()]) if field.kind in {"token", "choice"} else (lambda: variable.get().strip())
            if field.kind == "number":
                self._getters[key] = lambda: float(variable.get())
            if field.kind == 'column':
                self._column_variables[key] = variable
                preview = _lbl(block, text='', wraplength=600, justify='left')
                preview.pack(fill='x', padx=10, pady=(0, 8))
                def update(*_args):
                    sample = self._samples.get(variable.get())
                    if self._samples:
                        advice = advise_columns((field,), {key: variable.get()}, self._samples)[0]
                        if advice.present:
                            status = 'Found in this sample.'
                        elif advice.suggestion:
                            status = f'Configured header absent. Suggestion: {advice.suggestion} ({advice.reason}).'
                        elif advice.ambiguous:
                            status = 'Multiple possible matches: ' + ', '.join(advice.ambiguous) + '. Choose manually.'
                        elif not field.sample_required:
                            status = 'This header may be generated or needed only for an optional report.'
                        else:
                            status = 'Configured header absent from this sample. Choose a header or type one.'
                    else:
                        status = 'Choose a sample to check this mapping, or type a header manually.'
                    preview.configure(text=status + ((' Examples: ' + ' | '.join(sample)) if sample else ''))
                variable.trace_add('write', update)
                update()

    def _apply_suggestions(self):
        step = self.session.steps[self.index]
        values = {key: variable.get() for key, variable in self._column_variables.items()}
        advice = advise_columns(step.fields, values, self._samples)
        adopted = [item for item in advice if item.suggestion and not item.present]
        for item in adopted:
            self._column_variables[item.field].set(item.suggestion)
        self.notice.configure(text=(
            f'Applied {len(adopted)} suggestion(s) to this unsaved page. Review each mapping, then save.'
            if adopted else 'No unique suggestions available. Review the headers manually.'
        ))

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
            self._initial_values = values
        except (ValueError, OSError) as exc:
            self.notice.configure(text=str(exc))
            return False
        return True

    def _next(self):
        if not self._save():
            return
        if self.single_page:
            self._closed = True
            self.on_exit('Settings saved. Other setup pages keep their review state.')
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
            self._render_review()

    def _back(self):
        if self.index > 0 and self._save():
            self.index -= 1
            self._render()

    def _leave(self):
        if self._loading:
            self.notice.configure(text='Wait for the sample to finish reading before leaving.')
            return
        # Only committed pages survive; the current draft is deliberately not reviewed.
        if getattr(self, '_getters', None):
            try:
                dirty = {key: getter() for key, getter in self._getters.items()} != self._initial_values
            except ValueError:
                dirty = True
            if dirty:
                self.notice.configure(text='This page has unsaved changes. Save it, discard this draft, or stay here.')
                for child in self._footer.winfo_children():
                    child.destroy()
                def save_and_leave():
                    if self._save():
                        self._discard_and_leave()
                _btn(self._footer, 'Save & leave', save_and_leave, variant='primary').pack(side='right', padx=4)
                _btn(self._footer, 'Discard draft', self._discard_and_leave, variant='danger').pack(side='right', padx=4)
                _btn(self._footer, 'Stay here', self._stay).pack(side='left')
                return
        SetupWizard._discard_and_leave(self)

    def _stay(self):
        for child in self._footer.winfo_children():
            child.destroy()
        self._back_button = _btn(self._footer, 'Back', self._back)
        self._back_button.pack(side='left', padx=4)
        if self.index == 0:
            self._back_button.configure(state='disabled')
        _btn(self._footer, 'Pause setup', self._leave, variant='ghost').pack(side='left', padx=4)
        label = 'Save changes' if self.single_page else ('Review setup' if self.index == len(self.session.steps) - 1 else 'Save & next')
        self._next_button = _btn(self._footer, label, self._next, variant='primary')
        self._next_button.pack(side='right', padx=4)
        self.notice.configure(text='Continue editing. Your current draft is still here.')

    def _discard_and_leave(self):
        self._closed = True
        self.on_exit('Setup paused. Saved pages are retained; the current unsaved draft was discarded.')

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
                step = self.session.steps[self.index]
                self._samples_by_step[step.sample or step.id] = payload
                persistence_issue = ''
                if step.sample:
                    try:
                        save_last_paths(self.session.profile, {self.session.module: {step.sample: path}})
                    except (ValueError, OSError) as exc:
                        persistence_issue = f' Could not remember the selected file: {exc}'
                self._render(draft)
                self.notice.configure(text=f'Read {len(payload)} columns for this input. Review matching headers before saving.' + persistence_issue)
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
