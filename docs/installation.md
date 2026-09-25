# Installation and Launchers

Inventory Toolkit is a Python application. The CLI is the primary supported interface; the GUI is experimental.

## Requirements

- Python 3.10+
- packages from `requirements.txt`:
  - `pandas`
  - `openpyxl`
  - `xlrd`
  - `numpy`
  - `pydantic>=2,<3`
- Tkinter for native file dialogs and the experimental GUI

`xlrd` is required for the legacy `.xls` Cross Check demo fixture.

## Windows assisted setup

Run once:

```text
Setup Environment.bat
```

Behavior:

1. checks whether `python` is available;
2. if not, downloads the Python 3.11.9 Windows installer from `python.org`;
3. installs Python for the current user and adds it to `PATH`;
4. upgrades `pip`;
5. installs `requirements.txt`.

Normal CLI launch:

```text
Inventory Toolkit.bat
```

The launcher changes to the repository directory, enables UTF-8 behavior, prefers Windows Terminal when available, and falls back to the classic command prompt.

## Linux / macOS

Create and activate a virtual environment using your preferred shell, then install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Launch with:

```bash
./Inventory\ Toolkit.sh
```

or:

```bash
python cli.py
```

Some Linux distributions package Tkinter separately (for example `python3-tk`). Install the platform package if file dialogs or the GUI cannot start.

## Experimental GUI

From the repository root:

```bash
python -m gui.app
```

CustomTkinter is optional. If it is unavailable, the GUI falls back to standard Tkinter/ttk.

## Developer commands

```bash
pytest -q
python tools/ReleaseCheck.py
python tools/ReleaseCheck.py --release
```

For interactive developer tooling, launch the normal CLI, type the hidden command `debug`, select level 3, and open `D` / Developer Console.

## Working-directory behavior

The Windows and shell launchers still change to the repository root for convenience, but Inventory Toolkit no longer relies on the process CWD to locate its own resources. Profiles, built-in examples, logs, tools, and release references are anchored to the application root.

User-supplied relative workbook paths keep normal shell semantics and resolve from the directory where the command was invoked. For example, invoking `python C:/path/to/Inventory-Toolkit/cli.py` while standing in `C:/Work/Today` will still interpret `stock.xlsx` as `C:/Work/Today/stock.xlsx`, while the active profile continues to come from `C:/path/to/Inventory-Toolkit/profiles/`.

The experimental GUI is still normally launched as a module from the repository root (`python -m gui.app`) because Python module discovery is separate from Inventory Toolkit resource-path resolution.

## Upgrading dependencies

The project intentionally keeps `requirements.txt` small. Before changing package versions:

1. install the candidate environment cleanly;
2. run `pytest -q`;
3. run `python tools/ReleaseCheck.py --release`;
4. verify the experimental GUI can at least launch if the change affects Tk/Python packaging.

Do not infer dependency compatibility only from a successful import.
