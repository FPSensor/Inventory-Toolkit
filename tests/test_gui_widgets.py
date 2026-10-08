"""Stacked scroll pages must raise their layout container on both backends."""
from types import SimpleNamespace
import subprocess
import sys

from gui.widgets import BaseScrollable, USE_CTK


def test_scroll_page_raises_the_outer_layout_container():
    raised = []
    target = SimpleNamespace(tkraise=lambda *args: raised.append(args))
    view = SimpleNamespace(**({'_parent_frame': target} if USE_CTK else {'outer': target}))
    BaseScrollable.tkraise(view)
    assert len(raised) == 1


def test_ttk_fallback_uses_the_same_outer_container_rule():
    script = '''import sys
sys.modules['customtkinter'] = None
from types import SimpleNamespace
from gui.widgets import BaseScrollable, USE_CTK
assert not USE_CTK
raised = []
view = SimpleNamespace(outer=SimpleNamespace(tkraise=lambda *args: raised.append(args)))
BaseScrollable.tkraise(view)
assert len(raised) == 1
'''
    subprocess.run([sys.executable, '-c', script], check=True)
