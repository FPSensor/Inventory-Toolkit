"""Terminal output that survives redirection and the classic Windows console."""

import os
import sys

# Status symbols keep their meaning in plain text; decorative ones are dropped.
PLAIN_SYMBOLS = {
    "✅": "[OK]", "✓": "[OK]", "🟢": "[OK]",
    "❌": "[X]",
    "⚠": "[!]",
    "👉": ">",
    "⚡": "",
}
_VARIATION_SELECTOR = "️"


def utf8_output() -> None:
    """Make console symbols readable wherever the output goes.

    Windows uses the legacy code page for redirected output, where symbols such
    as ⚠️ or ✅ cannot be encoded and would stop the program. The classic
    Windows console (the window a .bat file opens) shows emoji as empty boxes,
    so there they are written as plain text instead.
    """
    for stream in (sys.stdout, sys.stderr):
        encoding = (getattr(stream, "encoding", "") or "").replace("-", "").lower()
        if encoding != "utf8" and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    if _classic_windows_console():
        sys.stdout = PlainSymbols(sys.stdout)
        sys.stderr = PlainSymbols(sys.stderr)


def _classic_windows_console() -> bool:
    """True for the old console host, which cannot draw emoji.

    ITK_SYMBOLS=emoji or ITK_SYMBOLS=plain overrides the detection.
    """
    choice = os.environ.get("ITK_SYMBOLS", "").strip().lower()
    if choice in {"emoji", "plain"}:
        return choice == "plain"
    if sys.platform != "win32" or not _is_terminal(sys.stdout):
        return False
    modern = ("WT_SESSION", "TERM_PROGRAM", "ConEmuANSI", "ALACRITTY_LOG", "WEZTERM_PANE")
    return not any(os.environ.get(name) for name in modern)


def _is_terminal(stream) -> bool:
    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError):
        return False


def plain_text(text: str) -> str:
    """Replace emoji with text the classic Windows console can draw."""
    if text.isascii():
        return text
    for symbol, plain in PLAIN_SYMBOLS.items():
        text = text.replace(symbol, plain)
    # Characters outside the basic plane are emoji the console cannot draw.
    return "".join(c for c in text if c != _VARIATION_SELECTOR and ord(c) <= 0xFFFF)


class PlainSymbols:
    """A text stream that writes emoji as plain text."""

    def __init__(self, stream):
        self._stream = stream

    def write(self, text):
        self._stream.write(plain_text(text))
        return len(text)

    def writelines(self, lines):
        for line in lines:
            self.write(line)

    def __getattr__(self, name):
        return getattr(self._stream, name)
