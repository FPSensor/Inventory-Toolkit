# Desktop GUI — RC preview

The desktop uses the same setup, validation and report engines as the CLI. Start it from the repository root:

```bash
python -m inventory_toolkit --interface gui
```

`build.prop` must include `gui` in `control-type`. Its `gui-stage` supplies the visible milestone label. The application release version remains 1.4.1; RC preview does not publish a new toolkit release.

## Workspace

Both CustomTkinter and the standard Tk/ttk fallback start dark. The sidebar contains profile selection, enabled workflows, setup, configuration and session text scaling. Disabled workflows remain visible but cannot run. Switching to a profile that disables the current workflow returns to the overview.

Workflow pages show Activity and Statistics in separate tabs, with a persistent last-successful-report panel. Overview, configuration, setup and profile creation use the available height without an empty results pane. Main forms scroll at smaller sizes. Text scaling is available at 100%, 115% and 130%.

Keyboard shortcuts: Ctrl+, opens Configuration, Ctrl+N opens New profile, and Escape requests leaving setup. Unsaved drafts are guarded.

## Profile creation

New profile is an embedded form, not a modal dialog. Enter a display name, optional description and only the workflows you need. A portable folder ID is generated automatically. New profiles use neutral data-owned defaults and whole product identifiers; they do not inherit the demo company's families or locations.

Creating a profile does not make every workflow ready. Its overview shows each selected module's review state and a direct setup action. Disabled modules retain their settings if enabled later.

## Guided module setup

The assistant uses friendly labels and short explanations rather than JSON variable names. Essential pages appear first; **Show additional settings** reveals cleanup, filters, output layout and other advanced choices. Conditional pages follow the selected data layout:

- scanner readings or a physical-count quantity table;
- stock columns by location or quantities recorded per row;
- source categories, prefix rules or unclassified products;
- independent purchase and retail mappings;
- optional product variants and revenue comparisons.

The step rail supports navigation and shows reviewed pages. Shared settings identify their effect on other modules, and unchanged shared reviews can be reused. A final review precedes Finish; finishing setup never starts a report automatically.

Choose an Excel sample on a mapping page to inspect headers and at most five rows. Unique suggestions are opt-in and remain drafts until saved. Samples are scoped by input role, so cost and sales lists stay separate. Explicit selections can be remembered for that workflow.

Save & next validates and persists a page. Back saves a valid page. Leaving an edited page offers Save & leave, Discard draft or Stay here. Invalid values remain available for correction. A missing required setting offers structured recovery to the relevant page; missing input headers retain explicit per-run default/abort behavior.

## Configuration

Configuration is an embedded searchable workspace. Search friendly section titles, field labels or help text; filter by workflow if useful. Selecting a section opens the same typed editor used by setup and returns to Configuration after saving. Shared sections appear once rather than requiring separate editor implementations.

Mappings, rules, groups and summaries use structured row editors. Choice fields show human-readable labels while saving the schema value. JSON is a storage format, not the primary configuration interface.

## Files and run options

Stock, Cross Check and YoY remember paths independently per profile. Switching profiles clears fields with no saved selection. Moving a profile folder does not relocate absolute last paths automatically.

YoY variants are optional and use the configured column label, such as flavor or presentation. Sales amounts are an explicit opt-in, reset on profile change, and mean **line revenue**, not unit price. Amounts are not multiplied by quantity again. Non-segmented annual comparison is separately opt-in; monthly reports use the configured annual-comparison preference.

Inspect selected files checks headers in a worker without generating a report, modifying the profile or applying guessed replacements. Input inspection and execution follow the selected grouping, metrics, variants and count layout.

## Execution and results

Only one task runs at a time. Profile and input controls lock during processing and recover their prior state after completion or failure. Workers report progress, statistics and completion through queues; only Tk's main thread updates widgets. Stage percentages describe completed work stages/sheets, not elapsed-time predictions.

Completion, warnings and failures stay inline. A failure does not force progress to 100%. The result panel retains the last successful report's absolute path, originating profile and duration, even after a subsequent failed run. Open report/folder are explicit actions and are disabled while processing.

Engines receive non-interactive saving behavior. Locked workbooks produce an actionable failure instead of an invisible terminal prompt. Close requests do not terminate a saving worker.

## Validation and remaining work

Real-widget checks cover Tk and CustomTkinter under a Linux display, including 900×680 windows, 130% scaling, embedded forms, profile guards and results-pane focus. Engine checks cover the existing demo and synthetic kiosk, greengrocer and grocery scenarios. See [testing_and_examples.md](testing_and_examples.md).

Native Windows/macOS rendering, keyboard/accessibility review and broader user testing remain pending. CustomTkinter is optional; the fallback remains supported. Developer certification stays in the optional `debug_tools` package and is not part of the GUI. This milestone is an RC preview, not a claim of native-platform release certification.

## Frontend structure

`gui/app.py` owns dispatch and session state. `config_hub.py` provides the searchable workspace, `setup_wizard.py` renders the shared catalog, `profile_dialog.py` provides embedded creation and `widgets.py` owns the dark design tokens and controls. Core owns profile persistence, typed configuration, setup state, input contracts and recovery codes. GUI code does not import the CLI package.

## Profile checks and recovery

Overview provides **Check profile / restore configuration**. The embedded panel checks enabled configuration, links recoverable issues to their setup page and lists saved configurations with labels/times. Save checkpoint creates a manual point. Restore first asks for inline confirmation and automatically checkpoints the current state. Workbooks and remembered paths are not restored.

File I/O runs in worker threads; controls stay locked while an operation runs, and the Tk event loop owns all widget updates. The panel must be left before switching profile or starting a report. Restoring refreshes review/navigation state and clears prior partial-setup permission. See [profile_history.md](profile_history.md) and [diagnostics.md](diagnostics.md).
