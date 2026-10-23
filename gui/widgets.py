"""Shared dark design tokens and accessible Tk/CustomTkinter controls."""
import sys
import tkinter as tk
from tkinter import ttk
import weakref

COLORS = dict(background='#0c1320', surface='#141f30', raised='#1b2a3e',
    entry='#0e1928', border='#30445e', text='#e8eff9', muted='#a8bad0',
    accent='#64b7f4', accent_hover='#84c7fa', positive='#73d8b4', warning='#f0c57c', error='#f09096')
FONT = 'Segoe UI' if sys.platform == 'win32' else 'DejaVu Sans'

try:
    import customtkinter as ctk
    ctk.set_appearance_mode('Dark')
    ctk.set_default_color_theme('blue')
    USE_CTK = True
    BaseWindow, BaseToplevel = ctk.CTk, ctk.CTkToplevel
    BaseButton, BaseLabel = ctk.CTkButton, ctk.CTkLabel
    BaseEntry, BaseTextbox = ctk.CTkEntry, ctk.CTkTextbox

    class BaseFrame(ctk.CTkFrame):
        def __init__(self, parent, **kwargs):
            kwargs.setdefault('fg_color', COLORS['surface'])
            kwargs.setdefault('corner_radius', 12)
            super().__init__(parent, **kwargs)

    class BaseScrollable(ctk.CTkScrollableFrame):
        def __init__(self, parent, **kwargs):
            kwargs.setdefault('fg_color', COLORS['surface'])
            kwargs.setdefault('corner_radius', 12)
            super().__init__(parent, **kwargs)

        def tkraise(self, aboveThis=None):
            self._parent_frame.tkraise(aboveThis)
except ImportError:
    ctk = None
    USE_CTK = False
    BaseWindow, BaseToplevel = tk.Tk, tk.Toplevel
    BaseFrame, BaseButton, BaseLabel = ttk.Frame, ttk.Button, ttk.Label
    BaseEntry, BaseTextbox = ttk.Entry, tk.Text


def _font(value):
    if isinstance(value, tuple) and value and value[0] == 'Arial':
        return (FONT, *value[1:])
    return value


def _btn(parent, text, command, **kwargs):
    variant = kwargs.pop('variant', 'secondary')
    kwargs = {key: value for key, value in kwargs.items() if value is not None}
    if USE_CTK:
        colors = {'primary': (COLORS['accent'], COLORS['background']),
            'danger': ('#713b4b', COLORS['text']), 'ghost': ('transparent', COLORS['muted'])}
        background, foreground = colors.get(variant, (COLORS['raised'], COLORS['text']))
        defaults = dict(height=38, corner_radius=9, fg_color=background, hover_color=COLORS['border'], text_color=foreground, font=(FONT, 12))
        defaults.update(kwargs)
        return ctk.CTkButton(parent, text=text, command=command, **defaults)
    allowed = {key: value for key, value in kwargs.items() if key in {'width', 'state', 'takefocus'}}
    return ttk.Button(parent, text=text, command=command, style=f'{variant.title()}.TButton', **allowed)


def _lbl(parent, text, **kwargs):
    kwargs = {key: value for key, value in kwargs.items() if value is not None}
    kwargs['font'] = _font(kwargs.get('font', (FONT, 12)))
    if USE_CTK:
        style = kwargs.pop('style', '')
        if style.startswith('Muted'):
            kwargs.setdefault('text_color', COLORS['muted'])
        return ctk.CTkLabel(parent, text=text, **kwargs)
    if 'text_color' in kwargs:
        kwargs['foreground'] = kwargs.pop('text_color')
    allowed = {key: value for key, value in kwargs.items() if key in {'font', 'wraplength', 'justify', 'anchor', 'width', 'padding', 'style', 'foreground', 'background'}}
    return ttk.Label(parent, text=text, **allowed)


def _entry(parent, textvariable=None, **kwargs):
    kwargs = {key: value for key, value in kwargs.items() if value is not None}
    if USE_CTK:
        defaults = dict(height=38, corner_radius=8, fg_color=COLORS['entry'], border_color=COLORS['border'], font=(FONT, 12))
        defaults.update(kwargs)
        return ctk.CTkEntry(parent, textvariable=textvariable, **defaults)
    allowed = {key: value for key, value in kwargs.items() if key in {'width', 'state', 'show'}}
    return ttk.Entry(parent, textvariable=textvariable, **allowed)


def _pack_btn(button, **kwargs):
    button.pack(**kwargs)
    return button


def _register_scroll(canvas):
    root = canvas.winfo_toplevel()
    if not hasattr(root, '_itk_scroll_canvases'):
        root._itk_scroll_canvases = weakref.WeakSet()
        def wheel(event):
            for target in list(root._itk_scroll_canvases):
                if not target.winfo_exists() or not target.winfo_viewable():
                    continue
                x, y = target.winfo_pointerxy()
                if target.winfo_rootx() <= x < target.winfo_rootx() + target.winfo_width() and target.winfo_rooty() <= y < target.winfo_rooty() + target.winfo_height():
                    if target.yview() == (0.0, 1.0):
                        return
                    amount = (-1 if event.num == 4 else 1) if event.num in (4, 5) else (-1 if event.delta > 0 else 1)
                    target.yview_scroll(amount * 3, 'units')
                    return 'break'
        for event in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
            root.bind_all(event, wheel, add='+')
    root._itk_scroll_canvases.add(canvas)


if not USE_CTK:
    class BaseScrollable(ttk.Frame):
        def __init__(self, parent, **kwargs):
            self.outer = ttk.Frame(parent)
            canvas = tk.Canvas(self.outer, bg=COLORS['surface'], highlightthickness=0)
            scroll = ttk.Scrollbar(self.outer, orient='vertical', command=canvas.yview)
            canvas.configure(yscrollcommand=scroll.set)
            canvas.pack(side='left', fill='both', expand=True)
            scroll.pack(side='right', fill='y')
            super().__init__(canvas)
            window = canvas.create_window((0, 0), window=self, anchor='nw')
            self.bind('<Configure>', lambda _event: canvas.configure(scrollregion=canvas.bbox('all')))
            canvas.bind('<Configure>', lambda event: canvas.itemconfigure(window, width=event.width))
            _register_scroll(canvas)

        def pack(self, **kwargs):
            self.outer.pack(**kwargs)

        def grid(self, **kwargs):
            self.outer.grid(**kwargs)

        def tkraise(self, *args):
            self.outer.tkraise(*args)


def apply_dark_theme(root):
    root.configure(**({'fg_color': COLORS['background']} if USE_CTK else {'bg': COLORS['background']}))
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('.', background=COLORS['surface'], foreground=COLORS['text'], font=(FONT, 12))
    style.configure('Muted.TLabel', foreground=COLORS['muted'])
    style.configure('TEntry', fieldbackground=COLORS['entry'], foreground=COLORS['text'], insertcolor=COLORS['text'], bordercolor=COLORS['border'], padding=8)
    style.configure('TCombobox', fieldbackground=COLORS['entry'], foreground=COLORS['text'], arrowcolor=COLORS['muted'], padding=7)
    style.map('TCombobox', fieldbackground=[('readonly', COLORS['entry'])], foreground=[('readonly', COLORS['text'])])
    style.configure('TButton', background=COLORS['raised'], foreground=COLORS['text'], padding=(12, 9), borderwidth=0)
    style.map('TButton', background=[('active', COLORS['border']), ('disabled', COLORS['surface'])], foreground=[('disabled', '#71859e')])
    style.configure('Primary.TButton', background=COLORS['accent'], foreground=COLORS['background'])
    style.map('Primary.TButton', background=[('active', COLORS['accent_hover']), ('disabled', COLORS['raised'])])
    style.configure('Ghost.TButton', background=COLORS['surface'], foreground=COLORS['muted'])
    style.configure('Nav.TButton', background=COLORS['surface'], foreground=COLORS['muted'], anchor='w')
    style.configure('NavActive.TButton', background=COLORS['border'], foreground=COLORS['text'], anchor='w')
    style.configure('Danger.TButton', background='#713b4b', foreground=COLORS['text'])
    style.configure('TCheckbutton', padding=5)
    style.map('TCheckbutton', background=[('active', COLORS['surface'])], foreground=[('disabled', '#71859e')])
    style.configure('TProgressbar', background=COLORS['accent'], troughcolor=COLORS['entry'], borderwidth=0)
    style.configure('TNotebook', background=COLORS['surface'])
    style.configure('TNotebook.Tab', background=COLORS['raised'], foreground=COLORS['text'], padding=9)
    style.configure('Treeview', background=COLORS['entry'], fieldbackground=COLORS['entry'], foreground=COLORS['text'], rowheight=32)
    for control in ('Listbox', 'Text', 'TCombobox*Listbox'):
        root.option_add(f'*{control}.background', COLORS['entry'])
        root.option_add(f'*{control}.foreground', COLORS['text'])
        root.option_add(f'*{control}.selectBackground', COLORS['border'])
        root.option_add(f'*{control}.selectForeground', COLORS['text'])
    root.option_add('*Text.insertBackground', COLORS['text'])
    root.option_add('*Text.font', (FONT, 11))
