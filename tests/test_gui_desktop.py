"""Optional real-widget smoke checks, run under a real or virtual X display."""
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.skipif(not os.environ.get('DISPLAY') and sys.platform not in {'win32', 'darwin'}, reason='A desktop display is required')
@pytest.mark.parametrize('backend', ['ttk', 'ctk'])
def test_desktop_navigation_and_small_scaled_forms(tmp_path, backend):
    if backend == 'ctk':
        pytest.importorskip('customtkinter')
    script = r'''
import os, sys, time, tkinter as tk
from pathlib import Path
if sys.argv[1] == 'ttk':
    sys.modules['customtkinter'] = None
from core import paths
from core.profile_creation import create_profile
paths.PROFILES_ROOT = Path(sys.argv[2])
profile = create_profile('Desktop Test', '', ['stock_processing'])
from gui.app import InventoryToolkitGUI
window = None
for attempt in range(30):
    try:
        window = InventoryToolkitGUI()
        break
    except tk.TclError as exc:
        if "couldn't connect" not in str(exc):
            raise
        time.sleep(.1)
assert window is not None
errors = []
window.report_callback_exception = lambda *error: errors.append(error)
def draw():
    for _ in range(3):
        window.update()
window.geometry('900x680')
draw()
assert window.active_profile.get() == profile
window._open_config_hub()
draw()
assert len(window._split.panes()) == 1
window._open_wizard('stock_processing', 'stock_layout')
draw()
assert window._setup_panel.session.profile == profile
window._change_scale('130%')
draw()
window._setup_panel._discard_and_leave()
draw()
window._open_new_profile()
draw()
assert window._setup_panel is not None
window._setup_panel._leave()
draw()
assert window._setup_panel is None
window._open_profile_recovery()
draw()
panel = window._setup_panel
def settle():
    deadline = time.monotonic() + 10
    while panel._busy and time.monotonic() < deadline:
        draw()
        time.sleep(.02)
    assert not panel._busy
settle()
assert panel._report is not None
from core.profile_history import create_checkpoint, list_checkpoints, restore_checkpoint
panel._run(lambda: create_checkpoint(profile), panel._created)
settle()
identifier = list_checkpoints(profile)[0]
panel._confirm_restore(identifier)
draw()
assert panel._confirmation == identifier
panel._cancel_restore()
assert panel._confirmation is None
panel._run(lambda: restore_checkpoint(profile, identifier), panel._restored)
settle()
assert 'Configuration restored' in panel._message
panel._leave()
draw()
assert window._setup_panel is None
window._show_module('stock_processing')
draw()
assert len(window._split.panes()) == 2
window._show_module('cross_check')
assert window._selected_module == 'stock_processing'
assert not errors, errors
window.destroy()
'''
    result = subprocess.run([sys.executable, '-c', script, backend, str(tmp_path / 'profiles')],
        cwd=Path(__file__).parents[1], text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
