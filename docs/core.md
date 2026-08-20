# ⚙️ Core Infrastructure Reference (`/core`)

The `/core` directory contains the foundational bricks that prevent the engine from crashing under hostile production environments.

## 1. `configuration_manager.py`
Responsible for multi-tenant profile isolation. It reads JSON files inside `profiles/<name>/configs/` and caches them in memory during execution to avoid disk I/O bottlenecks.

## 2. `logger.py`
Manages dual-channel logging:
* **Console Stream Handler:** Respects the hidden `-debug_level` argument (1 for Errors only, 2 for Warnings, 3 for Info).
* **Persistent File Handler:** Always writes a clean, timestamped audit trail to `logs/session.log`, allowing remote debugging (Magoya's best friend).

## 3. `system_utils.py` (The Bulletproof Safe Saver)
Retail workers constantly keep generated Excel reports open while trying to regenerate them. Standard Python throws a violent `PermissionError` and crashes. 
Our `safe_pandas_to_excel` and `safe_openpyxl_save` intercept this error, print an A.P.B. alert, and safely prompt the user to close the file or save a fallback copy (`_copy1.xlsx`).
