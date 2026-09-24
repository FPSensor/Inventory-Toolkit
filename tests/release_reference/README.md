# Release reference workbooks

This directory contains the approved **golden-master outputs** for the `demo`
profile. They are used by `tools/ReleaseCheck.py --release` to certify that a
candidate release still produces the expected Cross Check, Stock Processing,
and YoY workbooks.

The reference files are compared semantically, not byte-for-byte. The checker
verifies worksheet order, dimensions, values/formulas, relevant formatting,
merged ranges, filters, frozen panes, and row/column presentation metadata.
Temporary workbooks created during certification are deleted automatically.

`manifest.json` fingerprints every `examples/demo` input plus the demo profile
configuration. If one of those fixtures changes, release certification stops
and reports the stale reference instead of silently accepting the new data.

## Updating the reference

Only update the golden masters after intentionally changing business behavior,
the demo dataset, or the demo profile and manually reviewing the new output.

```bash
python tools/ReleaseCheck.py --update-reference
```

The command requires an explicit confirmation. It generates all three outputs
in a temporary directory first and updates the committed references only after
all workflows finish successfully.

After updating, review the changed reference workbooks and `manifest.json`
before committing them. Updating a reference is equivalent to declaring the
new output correct; it must never be used merely to make a failing release test
green.
