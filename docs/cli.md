# 🖥️ Command Line Interface Reference (`/cli`)

The CLI is designed to feel native, responsive, and completely frictionless.

## Module Breakdown
* **`menu.py`**: The central loop. Parses hidden arguments (`argparse.SUPPRESS`) to keep the user interface clean while allowing advanced debugging via terminal flags.
* **Launchers (`*_launcher.py`)**: Each engine has a dedicated launcher. They handle user prompts, invoke `tkinter.filedialog` for visual file browsing, and validate file existence before handing over execution control.
* **`config_menu.py` & `wizard.py`**: Provide an interactive JSON editor directly inside the terminal. The wizard sniffs column names (`nrows=0`) to auto-map configurations for new company profiles.
