# Experimental Desktop GUI

`gui/app.py` is the current desktop frontend for Inventory Toolkit.

Launch as a module from the repository root (Python module discovery requirement, not an application-resource CWD requirement):

```bash
python -m gui.app
```

## Status

Profile/configuration resources used by the GUI are anchored to the Inventory Toolkit application root and do not follow the process CWD.

The GUI is **experimental**. It is useful for testing the direction of a desktop workflow, but the CLI remains the primary supported interface and the reference surface for developer/release tooling.

Do not assume GUI behavior is feature-complete merely because an engine is exposed there.

## UI backends

The application attempts to use CustomTkinter when available. If it cannot import CustomTkinter, it falls back to standard Tkinter/ttk.

CustomTkinter is optional and is not required by `requirements.txt`.

## Current scope

Top-level GUI actions include:

- active-profile selection;
- new profile creation;
- setup guidance;
- graphical Configuration Hub;
- Cross Check tab;
- Stock Processing tab;
- YoY Reports tab.

## Configuration Hub

The graphical hub edits the current schema-v3 files for:

- family rules;
- active stores/regional groups;
- Stock cleaning/pricing/output;
- Cross Check settings;
- YoY input/output/report groups.

It exists alongside the CLI Configuration Hub. The CLI remains the more complete maintenance surface.

## Threading rule

Long-running engine calls must not block Tk's main loop. Worker threads may perform processing, but Tk widgets/message boxes must be updated from the main thread.

This constraint is architectural: engine/core code should report results/errors without requiring terminal interaction so both CLI and GUI can consume the same processing logic.

## Locked output files

Core safe-saving functions support non-interactive mode. GUI callers must receive an `OutputFileLockedError` rather than hanging on an invisible `input()` prompt.

## Error handling

The GUI validates obvious missing files/dates/configuration before launching a workflow and reports runtime failures through GUI dialogs.

For deeper diagnosis, reproduce with CLI debug level 2/3 when practical and inspect `logs/session.log`.

## Current limitations

- GUI UX is still being iterated and may change between minor versions.
- Developer Console/release maintenance lives in the CLI, not the GUI.
- CustomTkinter packaging is not yet part of the default dependency story.
- Automated GUI coverage is smaller than engine/CLI coverage.

These limitations are roadmap items rather than reasons to move business logic into `gui/app.py`.
