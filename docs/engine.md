# Engine Subsystems Reference

`engine/` contains the three business workflows and their shared classification logic.

The guiding rule is **useful responsibility boundaries**, not identical directory templates.

## Shared family classification — `engine/shared/families.py`

Family assignment is prefix-based and must preserve longest-prefix priority when rules overlap.

The current implementation builds a trie so a batch does not repeatedly scan the full Series for every configured prefix. The trie is an optimization; the business contract is:

- sanitize the article consistently;
- match configured prefixes;
- if multiple prefixes match, the longest/specific match wins regardless of family insertion order;
- equal-length duplicate prefixes retain the first configured family, so avoid assigning the same prefix to conflicting families;
- every article follows configured rules, including text resembling a review marker;
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

The engine supports consolidation and partial-count modes. Difference arithmetic follows `reconciliation.ignore_negative_system_stock_when_counted`: the default preserves counted quantity for counted articles with negative system stock; disabling it always computes physical minus system stock. System quantity comes from `input.quantity_column`. Both settings belong to the Cross Check profile.

Unknown/review data stays visible in output rather than being silently discarded.

### Output

The system-stock article column and exported article/family labels follow `general/catalog.json`; internal reconciliation still uses stable canonical keys. Cost/sales price-list columns remain owned by `cross_check/settings.json`.

The report includes family/article/system stock/physical count/difference and value totals. Positive/negative differences receive visual formatting. Header freezing/filtering are part of the generated workbook contract checked by golden-master certification.

---

## Stock Processing — `engine/stock_processing/`

Purpose: transform raw multi-branch stock into a cleaned, classified, priced, valued dataset plus configured summary sheets.

Input column names are selected by the profile. If a configured name is absent,
CLI and GUI can ask the operator to try that field's documented default for
the current run. An unattended engine call fails unless given an explicit
per-run override. Price-list parsing failures stop the workflow. Stock rows
with quantity but no article are omitted and reported with their source Excel
row numbers and quantities; a valid output can therefore carry warnings.

### Files

- `contracts.py` — resolves the validated profile into one immutable Stock Processing plan and owns private article/family pipeline keys.
- `data_processor.py` — raw-stock cleanup, deposit/region transforms, family assignment, and final output projection.
- `pricing.py` — isolated price-list column resolution and pivot normalization.
- `valuation.py` — unit-price attachment plus store/region cost and sales valuation.
- `generator.py` — thin stage orchestration and diagnostics.
- `excel_renderer.py` — detail and summary workbook rendering.

### Pipeline

Stock Processing now treats profile vocabulary as an input/output boundary rather than an implementation detail:

1. resolve the validated profile into one `StockProcessingPlan`;
2. read raw stock and validate the configured catalog article column;
3. apply configured text/numeric/drop-column cleanup;
4. convert the configurable article identity to a private internal key;
5. merge configured deposit/database columns and calculate regional quantities;
6. classify families into a private internal family key using the shared longest-prefix rules;
7. normalize/pivot pricing data independently of raw-stock column names;
8. attach unit prices and calculate store/regional cost and sales values;
9. project the configured output layout and restore the profile-owned article/family labels;
10. render configured summary sheets + raw-data sheet.

The private `__itk_*` keys must never escape into generated workbooks. This boundary lets a profile use names such as `SKU`/`Family` without forcing the core valuation pipeline to carry those external strings through every operation.

`output.base_columns` remains profile-owned. Historical canonical labels (`Artículo` / `Familias`) are accepted as compatibility aliases when the catalog vocabulary itself has been customized, so changing the catalog does not silently remove those fields from an otherwise untouched output layout.

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
- `stats.py` — monthly, group and overall completion comparisons.

### Pipeline

1. load historical sales;
2. parse configured date/quantity/sales-amount/article/store fields;
3. generate family classification when the source lacks a usable family column;
4. filter selected current period and aligned previous-year period;
5. segment by month if requested;
6. render each enabled metric (`units` and/or `sales`) using its configured input column;
7. render YoY comparison blocks when `annual_comparison` is enabled; for a non-segmented CLI/GUI run, the operator explicitly opts into these extra blocks (default: off), without changing the stored profile setting;
8. optionally include size breakdowns using the profile default or an explicit runtime override;
9. create monthly sheets when segmented, followed by a consolidated Full Report or yearly full reports for multi-year spans;
10. save safely.

Formula/layout changes are especially sensitive to regression and should be checked with strict golden-master certification.

---

## Final statistics contract

Statistics are separate from progress events and are emitted after a successful save. They summarize processed data; they do not alter workbook calculations.

| Workflow | Final summary | Interpretation |
| --- | --- | --- |
| Cross Check | Difference rows, surplus/shortage rows, scanner rows to review, families with differences, catalog articles and filtered articles | Surpluses/shortages count rows with positive/negative differences, not unit totals. Review readings count scanner rows marked for review before reconciliation filtering. |
| Stock | Input dimensions, excluded blank-article rows, output rows, families, unique articles assigned to the default family, units/cost/sale by active store and total | Store totals sum valued output columns; regional groups are not added again. Default-family counts reflect the assigned label, including any explicit rule using that label. |
| YoY | Period row counts, monthly current/prior-year comparison, configured group totals and overall total | Uses the sales metric when enabled, otherwise units. Totals are limited to configured branches; overall deduplicates branches across overlapping groups. |

YoY compares the selected date range with the aligned previous-year range, including partial months. Monthly statistics are produced even for non-segmented workbooks. Group totals use each group's unique branches; a single-branch group is labelled by its branch rather than claiming a multi-branch Global block. Overall is calculated independently over unique configured branches, not by summing potentially overlapping group totals. A zero prior-year total is shown as `N/A (prior year is zero)` rather than a fabricated percentage. The initial period row counts precede the configured-branch restriction.

## Price-list identifiers and workbook formatting

Stock and Cross Check independently resolve `pricing.article_tokenization`: `first_token` keeps the first whitespace-delimited token, while `whole` retains internal spaces after cleanup. Existing profiles use the historical `first_token` default. Stock formatting follows column roles and configured labels; Cross Check formatting uses bundled labels, and YoY size formulas use the configured size column with escaped criteria.

## Calling engines outside the CLI

Engines are intentionally callable from Python. Callers are responsible for supplying validated paths/options/configuration context and choosing interactive vs non-interactive save behavior where applicable.

New frontends should call engine/core APIs rather than importing CLI prompt functions.
