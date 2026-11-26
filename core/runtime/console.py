"""Terminal output that survives redirection on Windows."""

import sys


def utf8_output() -> None:
    """Write UTF-8 when output goes to a file or another program.

    Windows uses the legacy code page for redirected output, where symbols such
    as ⚠️ or ✅ cannot be encoded and would stop the program.
    """
    for stream in (sys.stdout, sys.stderr):
        encoding = (getattr(stream, "encoding", "") or "").replace("-", "").lower()
        if encoding != "utf8" and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
