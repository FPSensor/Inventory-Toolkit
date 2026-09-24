# Approved Release Reference Workbooks

This directory contains the committed golden-master outputs for the `demo` profile.

They answer a stronger question than a smoke test:

> Does the current candidate still produce the exact workbook behavior that maintainers previously reviewed and approved?

## Contents

- `workbooks/cross_check.xlsx`
- `workbooks/stock_processing.xlsx`
- `workbooks/yoy_reports.xlsx`
- `manifest.json`

## Certification

```bash
python tools/ReleaseCheck.py --release
```

The runner:

1. verifies the fixture/profile fingerprint from `manifest.json`;
2. generates new workflow outputs in temporary storage;
3. compares them semantically with these references;
4. runs repository verification;
5. removes generated temporary outputs.

## Semantic comparison

Reference comparison is not a raw file hash because `.xlsx` is a ZIP container with metadata that can vary independently of workbook behavior.

Meaningful workbook XML is canonicalized/compared, including values/formulas, sheet structure, styles, merges, filters, frozen panes, dimensions, and relevant row/column metadata.

When a fast digest differs, diagnostic comparison reports human-readable workbook differences where possible.

## Updating references

Only after intentionally changing expected business/output behavior or the fixture/profile:

```bash
python tools/ReleaseCheck.py --update-reference
```

The update is guarded, generates all three candidates before installation, and uses rollback protection.

After updating:

1. review the produced workbooks;
2. review `manifest.json`;
3. run `python tools/ReleaseCheck.py --release` again;
4. commit only if the new output is genuinely approved.

Never update the references merely because certification failed. Doing so would redefine a regression as expected behavior.

See [`../../docs/testing_and_examples.md`](../../docs/testing_and_examples.md) and [`../../docs/release_process.md`](../../docs/release_process.md).
