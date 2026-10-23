# Desktop GUI — Alpha Pre-Beta

`gui/app.py` is the current desktop frontend for Inventory Toolkit.

Launch as a module from the repository root (Python module discovery requirement, not an application-resource CWD requirement):

```bash
python -m gui.app
```

## Status

Profile/configuration resources used by the GUI are anchored to the Inventory Toolkit application root and do not follow the process CWD.

The GUI is **Alpha Pre-Beta**: a dark desktop workspace for the three workflows, graphical module setup and configuration recovery. The toolkit release version remains 1.4.1. The CLI remains the reference surface for developer/release tooling. Native desktop review on Windows/macOS is still required before declaring Beta.

Do not assume GUI behavior is feature-complete merely because an engine is exposed there.

## UI backends

The application attempts to use CustomTkinter when available. If it cannot import CustomTkinter, it falls back to standard Tkinter/ttk.

CustomTkinter is optional and is not required by `requirements.txt`.

## Current scope

Top-level GUI actions include:

- a profile overview showing each workflow's review state and its next setup page;
- active-profile selection;
- new profile creation;
- resumable graphical setup for each module;
- graphical Configuration Hub;
- Cross Check page;
- Stock Processing page;
- YoY Reports page.

YoY restores its last input/output paths for the active profile. For a
non-segmented report, the extra annual-comparison block beneath the full report
is off by default and can be enabled for that run. Segmented reports continue
to use the profile's annual-comparison setting.

## Progress and completion summaries

The status bar uses a determinate progress bar driven by engine stage events. An activity area retains concise stage messages and final statistics after the status changes to completion. Success, errors and collected warnings are retained inline; completion does not require dismissing a dialog. Drag the divider to resize the activity/results area.

Worker threads send progress, statistics and completion through queues; the Tk event loop updates widgets and inline notices. Percentages describe stage/sheet completion, not measured execution time. A failed task does not force the progress bar to 100%.

The statistics have the same engine-owned meaning as the CLI summaries; see [engine.md](engine.md#final-statistics-contract).

## Last successful output

A persistent result panel shows the last successful report's absolute path, originating profile and duration. The path can be selected and copied. Open report delegates to the system's associated application; Open folder opens its containing directory. Neither action runs automatically. Both are disabled while processing to avoid opening a workbook during a write.

The panel remains available after completion and after a later failed run; its label explicitly identifies it as the last successful output. Starting a new run clears the activity area for that run, while failures are recorded there and leave the previous successful report accessible. Selecting another profile does not relabel the originating profile of the result. This state lasts for the GUI session only.

## Configuration Hub

The graphical hub edits the current schema-v3 files for:

- family rules;
- active stores/regional groups;
- Stock cleaning/pricing/output;
- Cross Check settings;
- YoY input/output/report groups.

It exists alongside the CLI Configuration Hub. The CLI remains the more complete maintenance surface.

## Execution lifecycle

Only one processing task may run at a time. The GUI disables profile/actions and input controls across all three workflows while processing, then restores their previous states on success or failure. Controls already disabled by an option remain disabled. The activity area remains available for reviewing progress.

Close open profile/configuration windows before starting a workflow; this prevents an existing editor from changing settings during processing. Exit and window-close requests wait for the task to finish instead of terminating a saving worker. Failure to start a worker also restores the controls. After completion, existing input selections remain available for another run.

## Threading rule

Long-running engine calls must not block Tk's main loop. Worker threads may perform processing, but Tk widgets/message boxes must be updated from the main thread.

This constraint is architectural: engine/core code should report results/errors without requiring terminal interaction so both CLI and GUI can consume the same processing logic.

## Locked output files

Core safe-saving functions support non-interactive mode. GUI callers must receive an `OutputFileLockedError` rather than hanging on an invisible `input()` prompt.

## Error handling

The GUI validates obvious missing files/dates/configuration before launching a workflow and reports runtime failures through inline notices with explicit configuration actions when a structured error has a destination.

Use **Inspect selected files** on a workflow page for an optional, background read of up to five rows per selected workbook. The activity area lists column counts, required headers found or missing, and possible unique replacements. It respects the current YoY grouping/revenue/size choices. This inspection does not generate a report, apply default fallbacks, or modify the profile; running the workflow continues to use its normal confirmation and validation rules.

For deeper diagnosis, reproduce with CLI debug level 2/3 when practical and inspect `logs/session.log`.

## Current limitations

- GUI UX is still being iterated and may change between minor versions.
- Developer Console/release maintenance lives in the CLI, not the GUI.
- CustomTkinter packaging is not yet part of the default dependency story.
- Automated GUI coverage is smaller than engine/CLI coverage.

These limitations are roadmap items rather than reasons to move business logic into `gui/app.py`.

### Optional YoY sales amounts

`Include sales amounts (revenue), in addition to units` starts unchecked and resets when the active profile changes. Enable it to add monetary sections to all generated worksheets; leave it unchecked for units only, even if the profile lists both metrics. The selection does not modify the stored profile, and the worker receives the captured choice before processing starts. This control is separate from monthly segmentation, annual comparisons and variant breakdown.

Sales amounts are line revenue from the configured sales column, not unit prices. See the YoY formula contract in `docs/engine.md` for totals, percentage changes and zero-baseline behavior.

### Frontend structure

`gui/app.py` owns workflow dispatch and session state. `gui/config_hub.py` keeps the advanced editors, `gui/profile_dialog.py` owns profile creation, and `gui/widgets.py` owns shared controls and the dark Tk/CustomTkinter presentation. Reusable setup contracts live in `core/setup_catalog.py` and `core/setup_service.py`, independent of Tk and console input.

## Dark workspace and guided setup

Both backends start dark, including native ttk controls and advanced-editor listboxes. No light theme is enabled. The sidebar selects a workflow, active profile, module setup or advanced editing. Main workflow pages scroll independently; YoY options use multiple rows instead of a clipped horizontal strip. Text scaling is available at 100%, 115% and 130% for the current session.

Each setup page explains at most three related fields. Column fields accept manual names or sample-workbook headers; examples are limited to five rows and stay in memory. Sample reading uses a worker and all widget updates happen on Tk's thread. Different price-list pages can use different samples. Families, groups, aliases and summaries use editable rows instead of JSON entry. Prefix rules use longest-match priority; no business category is hardcoded. Shared steps explicitly identify their effect on other modules.

After choosing a sample, the page distinguishes an existing header from a missing configured header and a unique suggestion. Ambiguous suggestions require manual choice. The **Use unique suggestions** action updates only the current unsaved page; review each field and save to persist it. Samples are kept per setup page, so a cost-list sample never appears while configuring the sales list.

Save & next commits and reviews the page. Back also saves a valid page. Leave setup retains previously saved pages and discards the current unsaved page. A new profile starts with every module unconfigured. Starting that module opens its assistant. Partial setup offers Continue anyway or Complete setup; missing mandatory values produce a coded error with a direct setup action. Completing recovery does not run a report automatically. File selections and run options remain in the workflow page.

Advanced Configuration Hub editing remains available for experienced users. Native file choosers and operator decisions (such as a missing-column default fallback) may still open dialogs. Main workflow progress, completion and configuration recovery use inline feedback.

The design uses labeled settings with nearby explanations and validation at page boundaries, informed by the [VS Code Settings editor](https://code.visualstudio.com/docs/configure/settings) and [Qt wizard page validation](https://doc.qt.io/qt-6/qwizardpage.html). These are design references; the implementation remains Tk/CustomTkinter.

## Integrated configuration

Configuration is an embedded workspace, not a separate window or JSON-file list. Search human field names/help text and filter by enabled workflow. Shared sections appear once. Edit settings opens the same typed assistant used for setup, saves one section, and returns to the settings workspace. Run inputs remain intact. Workflow activation is managed through Profile overview.

## Desktop appearance and navigation

The desktop remains dark by default on both CustomTkinter and native ttk, with shared color/typography tokens and distinct primary/secondary actions. Navigation indicates the current workflow and disables workflows excluded by the profile. Activity and final statistics have separate result tabs. Use Ctrl+, for configuration, Ctrl+N for a new profile, and Escape to request leaving setup. The native scroll container supports the mouse wheel on Windows/macOS and X11.

## Guided setup workspace

The assistant has a step navigator, progress indicator, contextual explanations and a final review. Show additional settings expands the same catalog used by Configuration. Choosing an Excel sample offers matching headers and examples; samples are shared only across pages for that input role, and explicitly selected sample paths are remembered for later runs. Pausing with an unsaved draft presents Save & leave, Discard draft and Stay here inside the workspace. Finishing setup never starts a report automatically.
