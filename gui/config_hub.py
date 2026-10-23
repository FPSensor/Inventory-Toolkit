"""Embedded searchable configuration workspace backed by the shared assistant."""
import tkinter as tk

from core.module_preferences import enabled_modules
from core.setup_catalog import MODULE_LABELS
from core.setup_service import SetupSession
from gui.widgets import BaseFrame, BaseScrollable, USE_CTK, ctk, ttk, _btn, _lbl, _entry


class ConfigurationWorkspace(BaseFrame):
    def __init__(self, parent, profile, on_edit, on_workflows):
        super().__init__(parent)
        self.profile, self.on_edit = profile, on_edit
        self.query = tk.StringVar()
        self.module = tk.StringVar(value='All enabled workflows')
        header = BaseFrame(self)
        header.pack(fill='x', padx=20, pady=(16, 8))
        _lbl(header, text='Find a setting without opening JSON', font=('Arial', 21, 'bold')).pack(anchor='w', pady=(0, 6))
        _lbl(header, text='Search for product codes, quantities, prices, locations or report options.', wraplength=650, justify='left').pack(anchor='w')
        controls = BaseFrame(self)
        controls.pack(fill='x', padx=20, pady=8)
        _entry(controls, textvariable=self.query).pack(side='left', fill='x', expand=True, padx=(0, 10))
        labels = ['All enabled workflows', *[MODULE_LABELS[name] for name in enabled_modules(profile)]]
        combo = ctk.CTkComboBox(controls, values=labels, variable=self.module, state='readonly') if USE_CTK else ttk.Combobox(controls, values=labels, textvariable=self.module, state='readonly')
        combo.pack(side='left')
        _btn(self, 'Choose enabled workflows', on_workflows).pack(anchor='w', padx=20, pady=(0, 8))
        self.results = BaseScrollable(self)
        self.results.pack(fill='both', expand=True, padx=16, pady=(4, 16))
        self.query.trace_add('write', lambda *_: self.refresh())
        self.module.trace_add('write', lambda *_: self.refresh())
        self.refresh()

    def refresh(self):
        for child in self.results.winfo_children():
            child.destroy()
        query = self.query.get().strip().lower()
        count = 0
        shared = set()
        for module in enabled_modules(self.profile):
            label = MODULE_LABELS[module]
            if self.module.get() not in ('All enabled workflows', label):
                continue
            try:
                session = SetupSession(self.profile, module, include_advanced=True)
                for step in session.steps:
                    if step.shared and step.id in shared:
                        continue
                    searchable = ' '.join([step.title, *(field.label + ' ' + field.help for field in step.fields)]).lower()
                    if query and query not in searchable:
                        continue
                    if step.shared:
                        shared.add(step.id)
                    count += 1
                    card = BaseFrame(self.results)
                    card.pack(fill='x', padx=4, pady=6)
                    _lbl(card, text=step.title, font=('Arial', 15, 'bold')).pack(anchor='w', padx=14, pady=(12, 3))
                    scope = 'Shared across workflows' if step.shared else label
                    _lbl(card, text=scope, style='Muted.TLabel').pack(anchor='w', padx=14)
                    _lbl(card, text=' · '.join(field.label for field in step.fields), wraplength=590, justify='left').pack(anchor='w', padx=14, pady=6)
                    _btn(card, 'Edit settings', lambda name=module, step_id=step.id: self.on_edit(name, step_id)).pack(anchor='w', padx=14, pady=(2, 12))
            except (ValueError, OSError) as exc:
                _lbl(self.results, text=f'{label}: {exc}', wraplength=620).pack(fill='x', padx=12, pady=8)
        if not count:
            _lbl(self.results, text='No matching settings. Try a shorter term or choose another workflow.', wraplength=620).pack(anchor='w', padx=16, pady=24)
