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
Manages dual-channel logging:
* **Console Stream Handler:** Respects the hidden `-debug_level` argument (1 for Errors only, 2 for Warnings, 3 for Info).
* **Persistent File Handler:** Always writes a clean, timestamped audit trail to `logs/session.log`, allowing remote debugging (Magoya's best friend).

## 5. `system_utils.py` (The Bulletproof Safe Saver)
Retail workers constantly keep generated Excel reports open while trying to regenerate them. Standard Python throws a violent `PermissionError` and crashes. 
Our `safe_pandas_to_excel` and `safe_openpyxl_save` intercept this error. CLI callers keep the A.P.B. retry/copy prompt (`_copy1.xlsx`), while non-interactive callers such as the GUI receive an `OutputFileLockedError` instead of blocking on terminal input.
