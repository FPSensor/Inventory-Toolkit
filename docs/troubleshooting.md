# Troubleshooting

## `ModuleNotFoundError` when launching the GUI

Launch the GUI from the repository root as a module:

```bash
python -m gui.app
```

Do not use `python gui/app.py`; direct-script execution can give Python the wrong import root.

## `.xls` cannot be opened / missing `xlrd`

The official Cross Check demo system-stock file is legacy `.xls`.

Install project dependencies:

```bash
python -m pip install -r requirements.txt
```

Confirm:

```bash
python -c "import xlrd; print(xlrd.__version__)"
```

## Tkinter/file dialog does not start on Linux

Tkinter may be packaged separately from Python. Install your distribution's Tk package (commonly `python3-tk`) and retry.

## Output Excel is open/locked

In interactive CLI mode, safe saving offers retry/copy behavior. Close the workbook in Excel and retry, or choose a numbered copy where offered.

GUI/non-interactive callers receive a typed locked-output error instead of a terminal prompt.

## Profile validation fails

Open:

```text
K → Validate profile
```

or inspect the schema-v3 files described in [profiles.md](profiles.md).

Typical causes:

- missing/incorrect `version`;
- missing required column mapping;
- malformed JSON;
- incomplete store/price-list/report settings.

## `--release` says golden masters are stale

The demo inputs or demo profile/config changed since references were approved.

Investigate the fingerprint change. If intentional and reviewed, regenerate references with:

```bash
python tools/ReleaseCheck.py --update-reference
```

Do **not** update references until you understand why the fixture changed.

## `--release` reports a cell/formula/layout mismatch

Treat this as a business/output regression until proven intentional.

Use the diagnostic coordinates/expected values to identify the changed engine/renderer. Refactors that claim to preserve behavior should restore parity with existing references.

## Debug output is too quiet

From the main menu type:

```text
debug
```

Select level 2 or 3. Level 3 enables forensic events and the Developer Console.

Session log:

```text
logs/session.log
```

## Pytest works with `python -m pytest` but not `pytest`

The repository includes `pytest.ini` so both should work from the repository root. If a globally installed `pytest` still behaves differently, verify which executable/interpreter is being used:

```bash
python -m pytest -q
python -c "import sys; print(sys.executable)"
```

Prefer the virtual environment's interpreter.

## Compatibility warnings appear

The program is using a deprecated profile/storage/API path. See [legacy_compatibility.md](legacy_compatibility.md). The warning is intentionally informational at debug levels 2/3 so remaining migration work is visible before retirement.

## Release test is slow or memory-constrained

The strict runner uses isolated workflow subprocesses and may run them concurrently.

On a constrained machine:

```bash
python tools/ReleaseCheck.py --release --jobs 1
```

This trades elapsed time for lower concurrent resource use.

## Something failed but the error message is insufficient

Reproduce at debug level 3. The forensic logger includes stage timings, configuration/input context, row counts, output details, and tracebacks for instrumented error paths without dumping complete source datasets.
