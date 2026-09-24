# `engine/` — Business Processing

Inventory Toolkit's analytical/workbook-generation layer.

## Modules

- `inventory_cross_check/` — physical vs system reconciliation, variable-length article normalization, valuation, discrepancy workbook.
- `stock_processing/` — cleanup, store/region consolidation, family classification, pricing, valuation, summaries.
- `yoy_reports/` — current vs previous-year reporting, monthly segmentation, formulas, optional size breakdown.
- `shared/` — cross-workflow business algorithms such as family prefix classification.

## Design rule

Modules are split when a responsibility is independently complex/testable. YoY therefore has more renderer files than Cross Check or Stock Processing; the project does not enforce an arbitrary identical template.

Engines must remain callable without CLI prompts so both CLI and GUI can use the same business logic.

See [`../docs/engine.md`](../docs/engine.md).
