# Demo Dataset

`examples/demo/` is the sanitized reference fixture used for onboarding, smoke tests, and strict pre-release certification.

No personal/company-identifying data or credentials are intended to be present.

## Files

| File | Workflow | Purpose |
| --- | --- | --- |
| `cross_check_system_stock.xls` | Cross Check | legacy-format system article/stock master |
| `cross_check_physical_count.xlsx` | Cross Check | raw scanner/physical count input |
| `shared_cost_list.xlsx` | Cross Check + Stock Processing | cost pricing source |
| `shared_sales_price_list.xlsx` | Cross Check + Stock Processing | sales pricing source |
| `stock_processing_raw_stock.xlsx` | Stock Processing | raw multi-store inventory |
| `yoy_sales_history.xlsx` | YoY Reports | historical sales source |

The matching configuration lives in `profiles/demo/`.

## Release role

These files are part of the golden-master fixture. `tools/ReleaseCheck.py --release` fingerprints them together with the demo profile/configuration before comparing generated output against `tests/release_reference/`.

If a fixture changes intentionally, existing references become stale and must be reviewed/regenerated deliberately.

The `.xls` system-stock file requires `xlrd`, which is included in `requirements.txt`.

See [`../../docs/testing_and_examples.md`](../../docs/testing_and_examples.md).
