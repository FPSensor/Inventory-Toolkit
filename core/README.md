# Core Infrastructure

The backbone of the application providing essential services to all other modules.

## Services
*   **`configuration_manager.py`**: Safely loads, caches, and provides getter methods for all JSON configurations within the active profile.
*   **`logger.py`**: Manages standard output and persistent file logging (`logs/session.log`) with dynamic debug levels.
*   **`system_utils.py`**: Contains "Safe Savers" (`safe_pandas_to_excel`, `safe_openpyxl_save`) to prevent crashes when attempting to overwrite files currently opened by the user.
