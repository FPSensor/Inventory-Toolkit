# 🧠 Engine Subsystems Reference (`/engine`)

Engine modules are split only where a responsibility boundary is useful. Cross Check and Stock Processing use the compact processor/renderer/generator pattern; YoY has an additional worksheet renderer because workbook orchestration and worksheet/formula construction are independently complex.

## 1. Inventory Cross Check (`inventory_cross_check/`)

- **`data_processor.py`** — scan normalization and stock-difference arithmetic. `normalize_article()` treats system stock as the source of truth and selects the longest valid article prefix without assuming a fixed code length.
- **`excel_renderer.py`** — workbook formatting and output.
- **`generator.py`** — orchestration, filtering, pricing, and final output assembly.

## 2. Stock Processing (`stock_processing/`)

- **`data_processor.py`** — price-list normalization and margin calculations.
- **`excel_renderer.py`** — detail and summary workbook rendering.
- **`generator.py`** — stock cleanup, family assignment, valuation, regional aggregation, and orchestration.

## 3. YoY Sales Reports (`yoy_reports/`)

- **`data_processor.py`** — date filtering and optional family generation.
- **`sheet_renderer.py`** — a single report sheet, formulas, group blocks, totals, and optional size breakdowns.
- **`excel_renderer.py`** — workbook-level time segmentation, sheet naming, and safe saving.
- **`generator.py`** — orchestration.

## Shared rules (`shared/`)

`families.py` owns prefix classification. Its trie implementation preserves longest-prefix behavior while avoiding repeated full-Series regex scans.
