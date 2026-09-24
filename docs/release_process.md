# Release Process

This is the recommended release procedure for the current Inventory Toolkit 1.4 line.

It focuses on reproducibility and business-output verification. Version/changelog policy may evolve separately; do not skip certification because documentation/versioning work is still in progress.

## 1. Start from a clean worktree

```bash
git status --short
```

Know exactly which changes are intended for the release.

## 2. Install the intended release environment

```bash
python -m pip install -r requirements.txt
```

For a Cross Check release test using the official demo fixture, verify `xlrd` is available because the system-stock reference is legacy `.xls`.

## 3. Run focused development tests

```bash
pytest -q
python tools/IntegrityCheck.py
```

If you changed classification/performance-sensitive code, run the relevant stress diagnostics as well.

## 4. Run strict release certification

```bash
python tools/ReleaseCheck.py --release
```

A successful release candidate should finish with the three demo workflows matching their approved golden masters and the repository gate passing.

The generated candidate workbooks are temporary and removed automatically.

## 5. If certification says references are stale

Determine **why** the fixture fingerprint changed.

Expected examples:

- intentional demo input update;
- store/database mapping change;
- profile configuration change.

Unexpected fixture changes should be investigated/reverted.

Do not update references before understanding the change.

## 6. If output differs

Read the semantic diagnostic. Identify whether the change is:

- an intended business/output change;
- a harmless but intentionally approved layout change;
- an implementation regression.

For refactors that claim to preserve behavior, expected action is normally to fix the regression until existing golden masters pass.

## 7. Approving intentional new output

After manual review:

```bash
python tools/ReleaseCheck.py --update-reference
```

Then inspect the new committed-reference files/manifest and run:

```bash
python tools/ReleaseCheck.py --release
```

again.

Updating references is equivalent to declaring the new output correct.

## 8. Compatibility check

While the legacy layer exists:

```bash
python tools/RetireLegacyCompatibility.py
```

A release does **not** require compatibility retirement. The audit exists to tell you whether retirement is safe when you deliberately decide the migration window is over.

## 9. Manual surface checks

For changes affecting presentation/setup:

- launch the CLI;
- select/create a profile as relevant;
- open Configuration Hub / Guided Setup if changed;
- test the hidden `debug` selector if logging/developer tools changed;
- launch `python -m gui.app` for GUI-related changes.

Automation protects core behavior; it does not make UX review unnecessary.

## 10. Documentation and changelog

Before publishing:

- ensure README/docs match actual commands/config structure;
- update version metadata where the release process requires it;
- prepare CHANGELOG from the actual diff/history rather than memory;
- verify the release archive does not contain `.git`, caches, logs, or operational files that should remain local.

## Debug-level shortcut

Most developer/release operations can be run without leaving Inventory Toolkit:

```text
main menu → type debug → level 3 → D
```

The Developer Console exposes pytest, quick verification, demo smoke, strict release certification, golden-master update, log tail, and compatibility lifecycle while present.
