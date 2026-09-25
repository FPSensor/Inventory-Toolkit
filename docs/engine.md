# Engine Subsystems Reference

`engine/` contains the three business workflows and their shared classification logic.

The guiding rule is **useful responsibility boundaries**, not identical directory templates.

## Shared family classification — `engine/shared/families.py`

Family assignment is prefix-based and must preserve longest-prefix priority when rules overlap.

The current implementation builds a trie so a batch does not repeatedly scan the full Series for every configured prefix. The trie is an optimization; the business contract is:

- sanitize the article consistently;
- match configured prefixes;
- if multiple prefixes match, the longest/specific match wins;
- unresolved/default behavior follows profile configuration.

Performance changes must demonstrate parity against the reference implementation/tests.

---

## Inventory Cross Check — `engine/inventory_cross_check/`

Purpose: reconcile physical scanner counts against system stock, calculate differences, classify them, and attach cost/sales valuation.

### Files

- `data_processor.py` — scan/article normalization and difference arithmetic.
- `generator.py` — workflow orchestration, loading/filtering/consolidation/pricing.
- `excel_renderer.py` — final workbook creation and formatting.

### Article normalization

`normalize_article()` is one of the core business invariants.

Scanner data may concatenate an unknown-length article code, size, color, or other suffix without a reliable delimiter. Example:

```text
11111-261XXLH1
```

A fixed slice is invalid because article lengths vary.

The algorithm uses the system-stock article master as evidence:

1. sanitize the raw scanner value;
2. if the full value is a known article, keep it;
3. otherwise find known articles that are prefixes of the scanner value;
4. choose the longest valid match;
5. if none exists, preserve the original scanner value with `REVISAR |`.

This behavior must not be replaced by heuristic truncation.

### Reconciliation behavior

The engine supports consolidation and partial-count modes. Difference arithmetic includes business handling for negative system stock and is covered by integrity/tests.

Unknown/review data stays visible in output rather than being silently discarded.

### Output

The report includes family/article/system stock/physical count/difference and value totals. Positive/negative differences receive visual formatting. Header freezing/filtering are part of the generated workbook contract checked by golden-master certification.

---

## Stock Processing — `engine/stock_processing/`

Purpose: transform raw multi-branch stock into a cleaned, classified, priced, valued dataset plus configured summary sheets.

### Files

- `data_processor.py` — pricing-list normalization and margin/value calculations.
- `generator.py` — cleanup, store/region consolidation, family assignment, pricing, valuation, output preparation.
- `excel_renderer.py` — detail and summary workbook rendering.

### Pipeline

Typical stages:

1. read raw stock and configured price lists;
2. normalize configured text/numeric columns;
3. drop configured unwanted columns;
4. map raw stock database columns to active stores;
5. calculate configured regional groups;
6. classify article families;
7. normalize/pivot pricing data;
8. attach cost/sales values;
9. calculate valuation/margins;
10. select output columns;
11. render configured summary sheets + raw-data sheet.

The output layout is profile-owned under `stock_processing/settings.json`.

---

## YoY Sales Reports — `engine/yoy_reports/`

Purpose: compare a selected sales period with the corresponding previous-year period, optionally segmented by month and size.

YoY has more renderer modules because worksheet formulas/layout became substantial enough to justify independent boundaries.

### Files

- `data_processor.py` — date preparation/filtering and optional family generation.
- `generator.py` — high-level workflow orchestration.
- `excel_renderer.py` — workbook/time-segment orchestration and saving.
- `sheet_renderer.py` — worksheet-level orchestration.
- `current_sales_renderer.py` — current-period blocks and optional size breakdowns.
- `comparison_renderer.py` — YoY comparison blocks/formulas.
- `styles.py` — shared worksheet style primitives.
- `metrics.py` — configured metric resolution and report-group/branch validation.

### Pipeline

1. load historical sales;
2. parse configured date/quantity/sales-amount/article/store fields;
3. generate family classification when the source lacks a usable family column;
4. filter selected current period and aligned previous-year period;
5. segment by month if requested;
6. render each enabled metric (`units` and/or `sales`) using its configured input column;
7. render YoY comparison blocks only when `annual_comparison` is enabled;
8. optionally include size breakdowns using the profile default or an explicit runtime override;
9. create Full Report and/or period sheets;
10. save safely.

Formula/layout changes are especially sensitive to regression and should be checked with strict golden-master certification.

---

## Calling engines outside the CLI

Engines are intentionally callable from Python. Callers are responsible for supplying validated paths/options/configuration context and choosing interactive vs non-interactive save behavior where applicable.

New frontends should call engine/core APIs rather than importing CLI prompt functions.
