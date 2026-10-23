"""Embedded profile onboarding: a name and only the workflows you need."""
import tkinter as tk

from core.profile_creation import create_profile, profile_slug
from core.setup_catalog import MODULE_LABELS
from gui.widgets import BaseFrame, BaseScrollable, USE_CTK, ctk, ttk, _btn, _lbl, _entry, COLORS


class NewProfilePanel(BaseFrame):
    def __init__(self, parent, profile, on_created, on_cancel):
        super().__init__(parent)
        self.profile = profile
        self.on_created, self.on_cancel = on_created, on_cancel
        self.name = tk.StringVar()
        self.description = tk.StringVar()
        self.modules = {name: tk.BooleanVar(value=True) for name in MODULE_LABELS}
        content = BaseScrollable(self)
        content.pack(fill='both', expand=True, padx=24, pady=16)
        _lbl(content, text='Make this workspace yours', font=('Arial', 25, 'bold')).pack(anchor='w', pady=(12, 8))
        _lbl(content, text='Create a profile, choose your workflows, then configure each one with its own files. You can enable more workflows later.', wraplength=670, justify='left', style='Muted.TLabel').pack(anchor='w', pady=(0, 20))
        _lbl(content, text='Profile name', font=('Arial', 14, 'bold')).pack(anchor='w', pady=(4, 6))
        entry = _entry(content, textvariable=self.name)
        entry.pack(fill='x', padx=(0, 16))
        self.folder = _lbl(content, text='A portable folder name will be generated automatically.', style='Muted.TLabel')
        self.folder.pack(anchor='w', pady=(6, 18))
        _lbl(content, text='Description (optional)').pack(anchor='w', pady=(0, 6))
        _entry(content, textvariable=self.description).pack(fill='x', padx=(0, 16), pady=(0, 20))
        _lbl(content, text='What would you like to do?', font=('Arial', 16, 'bold')).pack(anchor='w', pady=(0, 8))
        details = {'cross_check': 'Compare recorded stock with a physical count.',
            'stock_processing': 'Clean quantities and value stock by location.',
            'yoy_reports': 'Compare sales periods, quantities and optional revenue.'}
        for name, variable in self.modules.items():
            row = BaseFrame(content)
            row.pack(fill='x', pady=5, padx=(0, 16))
            cls = ctk.CTkCheckBox if USE_CTK else ttk.Checkbutton
            cls(row, text=MODULE_LABELS[name], variable=variable).pack(anchor='w', padx=12, pady=(10, 2))
            _lbl(row, text=details[name], style='Muted.TLabel', wraplength=580).pack(anchor='w', padx=16, pady=(0, 12))
        self.notice = _lbl(self, text='Only enabled workflows will ask for setup.', wraplength=680, justify='left', style='Muted.TLabel')
        self.notice.pack(fill='x', padx=24, pady=8)
        self.actions = BaseFrame(self)
        self.actions.pack(fill='x', padx=24, pady=16)
        _btn(self.actions, 'Cancel', self._leave, variant='ghost').pack(side='left')
        self.create_button = _btn(self.actions, 'Create profile', self._submit, variant='primary')
        self.create_button.pack(side='right')
        self.name.trace_add('write', self._update)
        for variable in self.modules.values():
            variable.trace_add('write', self._update)
        self._update()
        entry.focus_set()

    def _update(self, *_args):
        try:
            slug = profile_slug(self.name.get())
            self.folder.configure(text=f'Profile folder: {slug}')
            valid = any(variable.get() for variable in self.modules.values())
        except ValueError:
            valid = False
            self.folder.configure(text='Enter a name to generate the profile folder.')
        self.create_button.configure(state='normal' if valid else 'disabled')

    def _submit(self):
        try:
            profile = create_profile(self.name.get(), self.description.get(),
                [name for name, variable in self.modules.items() if variable.get()])
        except (ValueError, OSError) as exc:
            self.notice.configure(text=f'Could not create profile: {exc}', **({'text_color': COLORS['error']} if USE_CTK else {'foreground': COLORS['error']}))
            return
        self.on_created(profile)

    def _leave(self):
        if self.name.get().strip() or self.description.get().strip():
            self.notice.configure(text='This profile has not been created. Discard this draft or continue editing.')
            _btn(self.actions, 'Discard draft', self.on_cancel, variant='danger').pack(side='left', padx=8)
        else:
            self.on_cancel()
