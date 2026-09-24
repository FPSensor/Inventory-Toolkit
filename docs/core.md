# ⚙️ Core Infrastructure Reference (`/core`)

The `/core` directory contains the foundational bricks that prevent the engine from crashing under hostile production environments.

## 1. `configuration_manager.py`
Responsible for multi-tenant profile isolation. It reads JSON files inside `profiles/<name>/configs/` and caches them in memory during execution to avoid disk I/O bottlenecks.


## 2. `business_schema.py`
Centralizes external workbook vocabulary such as `Artículo`, `Familias`, `Costo`, and `REVISAR |`. These labels remain Spanish where required by real business files while implementation identifiers stay English.

<!-- BEGIN LEGACY_COMPATIBILITY -->
## 3. `legacy_config.py` and `profile_config.py`
Isolate historical v1/v2 serialized keys and migrate them into the current v3 module-oriented schema. Built-in modules do not consume the legacy Spanish configuration API.
Debug diagnostics and the guarded retirement process are documented in `legacy_compatibility.md`.
<!-- END LEGACY_COMPATIBILITY -->

## 4. `logger.py`
Manages runtime-reconfigurable dual-channel logging. The CLI accepts the historical hidden `-debug_level`/`--debug-level` startup flag, but the normal developer workflow is now to type the hidden command `debug` in the main menu and select the verbosity without restarting.

* **Level 1 — Operator:** errors only.
* **Level 2 — Diagnostics:** operational milestones, warnings, timing information, and compatibility notices.
* **Level 3 — Forensic:** DEBUG-level structured events including profile/config resolution, input workbook dimensions and columns, cleaning/merge decisions, normalization review counts, result sizes, generated sheets, save attempts, developer-tool commands, and exception tracebacks. Raw spreadsheet rows are intentionally not dumped to the log.
* **Persistent File Handler:** writes the current session to `logs/session.log` using timestamp, process/thread, source module, and line-number metadata. The level-3 Developer Console can display the current log tail directly.

Changing levels at runtime reuses the existing handlers, so enabling forensic mode does not truncate the current session log.

## 5. `system_utils.py` (The Bulletproof Safe Saver)
Retail workers constantly keep generated Excel reports open while trying to regenerate them. Standard Python throws a violent `PermissionError` and crashes. 
Our `safe_pandas_to_excel` and `safe_openpyxl_save` intercept this error. CLI callers keep the A.P.B. retry/copy prompt (`_copy1.xlsx`), while non-interactive callers such as the GUI receive an `OutputFileLockedError` instead of blocking on terminal input.
