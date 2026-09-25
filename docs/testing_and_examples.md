# Testing, Demo Fixtures, and Golden Masters

Inventory Toolkit uses several layers of verification because no single test style can protect a workbook-processing application.

## 1. Pytest — `tests/`

Run:

```bash
pytest -q
```

Coverage includes configuration, core utilities, logger/debug tooling, business edge cases, compatibility behavior while present, and golden-master comparator behavior.

Important examples include:

- exact/longest-prefix article normalization;
- `REVISAR |` fallback;
- difference arithmetic including negative stock cases;
- stock margin/zero handling;
- config schema/migration behavior;
- configurable family fallback parity across scalar/batch classification;
- YoY metric/annual-comparison/group contracts;
- logger/runtime-debug behavior;
- release-reference semantic comparison;
- application-resource CWD independence and foreign-CWD pollution protection.

Tests should target stable behavior rather than implementation trivia where possible.

## 2. IntegrityCheck — `tools/IntegrityCheck.py`

A focused logical diagnostic suite covering core invariants and representative calculations, including application-root path ownership checks executed from a foreign temporary CWD.

Run:

```bash
python tools/IntegrityCheck.py
```

It complements pytest; it does not replace it and should not claim universal correctness beyond the checks it actually runs.

## 3. StressTests — `tools/StressTests.py`

Diagnostic/performance checks for classification and other stress-sensitive operations.

Performance output is evidence, not a guarantee: a measured speedup below `1.0x` means the candidate was slower and should be treated accordingly.

## 4. Demo fixture — `examples/demo/`

Sanitized, structure-preserving workbooks cover all three workflows:

| File | Used by |
| --- | --- |
| `cross_check_system_stock.xls` | Cross Check system master |
| `cross_check_physical_count.xlsx` | Cross Check scanner count |
| `shared_cost_list.xlsx` | Cross Check + Stock Processing |
| `shared_sales_price_list.xlsx` | Cross Check + Stock Processing |
| `stock_processing_raw_stock.xlsx` | Stock Processing |
| `yoy_sales_history.xlsx` | YoY Reports |

The demo profile under `profiles/demo/` supplies the corresponding schema-v3 rules.

## 5. Quick repository gate

```bash
python tools/ReleaseCheck.py
```

Runs the lightweight pre-release repository checks, including compilation/tests/integrity/profile validation and compatibility audit while relevant.

Use during normal development.

## 6. Demo workflow smoke test

```bash
python tools/ReleaseCheck.py --demo
```

Runs Cross Check, Stock Processing, and YoY against the demo fixture. It verifies that each workflow completes and produces plausible expected structure.

Generated outputs live in temporary storage and are deleted after the run.

## 7. Strict golden-master certification

```bash
python tools/ReleaseCheck.py --release
```

This is the preferred final pre-release test.

It:

1. fingerprints demo/profile inputs;
2. rejects stale reference data before certifying output;
3. executes all three workflows in isolated subprocesses;
4. compares generated workbooks with approved references under `tests/release_reference/`;
5. runs the repository gate;
6. removes temporary generated workbooks.

Workflows can run concurrently. Use `--jobs 1` if a constrained machine needs serial execution.

### Why comparison is semantic

`.xlsx` is a ZIP container. Byte-for-byte file hashes can change because ZIP timestamps or non-business packaging metadata changed.

The release-reference comparator canonicalizes meaningful workbook XML and checks values/formulas, structure, styles, merges, filters, frozen panes, dimensions, and relevant row/column metadata.

On a digest mismatch it can open the workbooks and report human-readable differences such as sheet/cell coordinates and expected vs actual values.

## 8. Reference manifest

`tests/release_reference/manifest.json` fingerprints:

- all files under the demo input fixture;
- demo profile metadata;
- demo configuration JSON.

If a store/database/config/demo input changes, `--release` reports the reference as stale instead of silently accepting old expected output.

## 9. Updating golden masters

Only after an **intentional and reviewed** change:

```bash
python tools/ReleaseCheck.py --update-reference
```

The command requires an explicit confirmation and generates all three candidates before replacing any approved reference. Installation is rollback-protected.

Afterward:

1. inspect the new workbook outputs manually;
2. inspect `manifest.json` changes;
3. run `--release` again;
4. commit the references only if the new behavior is truly intended.

Never update golden masters merely because a test failed.

## Development override for legacy `.xls`

The official Cross Check demo uses `.xls` and therefore requires `xlrd`.

During development, `--cross-system PATH` can point release/demo execution at an equivalent system-stock workbook. This override is intentionally forbidden when **updating** approved references so the committed manifest and committed golden masters cannot describe different fixtures.

## Reference directory

See [`../tests/release_reference/README.md`](../tests/release_reference/README.md) for the local golden-master contract.
