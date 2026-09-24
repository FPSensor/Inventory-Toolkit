# Command Line Interface (CLI)

The interactive presentation layer of Inventory Toolkit. It bridges the user's inputs with the internal engine.

## Components
*   **`menu.py`**: The main entry point and routing hub.
*   **Launchers (`cross_check_launcher.py`, etc.)**: Gather files, options, and parameters via interactive prompts before triggering the engine.
*   **`config_menu.py`**: Interactive JSON editor for modifying profiles without leaving the terminal.
*   **`wizard.py`**: Auto-detects Excel columns and generates boilerplate configurations for new profiles.
*   **`utils.py`**: Helper functions for screen clearing, file dialogs (Tkinter), and JSON I/O.


## Hidden debug console

Typing `debug` in the main menu opens the runtime verbosity selector without requiring a restart. Level 3 exposes the Developer Console for pytest, repository/release checks, golden-master maintenance, session-log inspection, and (while present) guarded legacy-compatibility retirement. The hidden startup flags remain supported for automation.
