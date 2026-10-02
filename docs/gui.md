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

YoY restores its last input/output paths for the active profile. For a
non-segmented report, the extra annual-comparison block beneath the full report
is off by default and can be enabled for that run. Segmented reports continue
to use the profile's annual-comparison setting.

## Progress and completion summaries

The status bar uses a determinate progress bar driven by engine stage events. An activity area retains concise stage messages and final statistics after the status changes to completion. The success dialog includes the final summary and any collected warnings.

Worker threads send progress, statistics and completion through queues; the Tk event loop updates widgets and dialogs. Percentages describe stage/sheet completion, not measured execution time. A failed task does not force the progress bar to 100%.

The statistics have the same engine-owned meaning as the CLI summaries; see [engine.md](engine.md#final-statistics-contract).

## Last successful output

A persistent result panel shows the last successful report's absolute path, originating profile and duration. The path can be selected and copied. Open report delegates to the system's associated application; Open folder opens its containing directory. Neither action runs automatically. Both are disabled while processing to avoid opening a workbook during a write.

The panel remains available after dismissing the success dialog and after a later failed run; its label explicitly identifies it as the last successful output. Starting a new run clears the activity area for that run, while failures are recorded there and leave the previous successful report accessible. Selecting another profile does not relabel the originating profile of the result. This state lasts for the GUI session only.

## Configuration Hub

The graphical hub edits the current schema-v3 files for:

- family rules;
- active stores/regional groups;
- Stock cleaning/pricing/output;
- Cross Check settings;
- YoY input/output/report groups.

It exists alongside the CLI Configuration Hub. The CLI remains the more complete maintenance surface.

## Execution lifecycle

Only one processing task may run at a time. The GUI disables profile/actions and input controls across all three workflows while processing, then restores their previous states on success or failure. Controls already disabled by an option remain disabled. Tabs and the activity area remain available for reviewing progress.

Close open profile/configuration windows before starting a workflow; this prevents an existing editor from changing settings during processing. Exit and window-close requests wait for the task to finish instead of terminating a saving worker. Failure to start a worker also restores the controls. After completion, existing input selections remain available for another run.

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
