"""Shared dark Tk/CustomTkinter widgets and appearance settings."""
import tkinter as tk
from tkinter import ttk

try:
    import customtkinter as ctk
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")
    USE_CTK = True
    BaseWindow, BaseToplevel = ctk.CTk, ctk.CTkToplevel
    BaseFrame, BaseButton, BaseLabel = ctk.CTkFrame, ctk.CTkButton, ctk.CTkLabel
    BaseEntry, BaseTextbox, BaseScrollable = ctk.CTkEntry, ctk.CTkTextbox, ctk.CTkScrollableFrame
except ImportError:
    ctk = None
    USE_CTK = False
    BaseWindow, BaseToplevel = tk.Tk, tk.Toplevel
    BaseFrame, BaseButton, BaseLabel = ttk.Frame, ttk.Button, ttk.Label
    BaseEntry, BaseTextbox = ttk.Entry, tk.Text

def _btn(parent, text, command, **kw):
    """Create a button with consistent styling."""
    if USE_CTK:
        return ctk.CTkButton(parent, text=text, command=command, **kw)
    else:
        b = ttk.Button(parent, text=text, command=command)
        return b


def _lbl(parent, text, **kw):
    if USE_CTK:
        return ctk.CTkLabel(parent, text=text, **kw)
    return ttk.Label(parent, text=text)


def _entry(parent, textvariable=None, **kw):
    if USE_CTK:
        return ctk.CTkEntry(parent, textvariable=textvariable, **kw)
    return ttk.Entry(parent, textvariable=textvariable)


def _pack_btn(btn, **kw):
    btn.pack(**kw)
    return btn




if not USE_CTK:
    class BaseScrollable(ttk.Frame):
        def __init__(self, parent, **kwargs):
            self.outer = ttk.Frame(parent)
            canvas = tk.Canvas(self.outer, bg="#171d27", highlightthickness=0)
            scroll = ttk.Scrollbar(self.outer, orient="vertical", command=canvas.yview)
            canvas.configure(yscrollcommand=scroll.set)
            canvas.pack(side="left", fill="both", expand=True)
            scroll.pack(side="right", fill="y")
            super().__init__(canvas)
            window = canvas.create_window((0, 0), window=self, anchor="nw")
            self.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))

        def pack(self, **kwargs):
            self.outer.pack(**kwargs)

        def grid(self, **kwargs):
            self.outer.grid(**kwargs)

        def tkraise(self, *args):
            self.outer.tkraise(*args)


def apply_dark_theme(root):
    """Explicitly style the ttk fallback; never inherit a light OS theme."""
    root.configure(**({"fg_color": "#111722"} if USE_CTK else {"bg": "#111722"}))
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background="#171d27", foreground="#e3e9f3", font=("Arial", 12))
    style.configure("TEntry", fieldbackground="#222c3b", foreground="#e3e9f3", insertcolor="#e3e9f3")
    style.configure("TCombobox", fieldbackground="#222c3b", foreground="#e3e9f3", arrowcolor="#e3e9f3")
    style.map("TCombobox", fieldbackground=[("readonly", "#222c3b")], foreground=[("readonly", "#e3e9f3")])
    style.configure("TButton", background="#294c79", foreground="#ffffff", padding=8)
    style.map("TButton", background=[("active", "#386598"), ("disabled", "#253040")])
    style.configure("TNotebook", background="#171d27")
    style.configure("TNotebook.Tab", background="#222c3b", foreground="#e3e9f3")
    root.option_add("*Listbox.background", "#222c3b")
    root.option_add("*Listbox.foreground", "#e3e9f3")
    root.option_add("*Text.background", "#222c3b")
    root.option_add("*Text.foreground", "#e3e9f3")
    root.option_add("*Text.insertBackground", "#e3e9f3")
    root.option_add("*TCombobox*Listbox.background", "#222c3b")
    root.option_add("*TCombobox*Listbox.foreground", "#e3e9f3")
