# Profiles and Configuration Schema v3

Profiles separate deployment/business differences from engine source code.

A profile may represent a company, environment, test fixture, or alternate workflow configuration. New built-in code should consume the current typed configuration API rather than hard-coded values or legacy projections.

## Profile tree

```text
profiles/<name>/
├── profile.json
├── configs/
│   ├── general/
│   │   ├── catalog.json
│   │   ├── families.json
│   │   └── network.json
│   ├── stock_processing/
│   │   └── settings.json
│   ├── cross_check/
│   │   └── settings.json
│   └── yoy_reports/
│       └── settings.json
└── last_paths.json               # local runtime convenience state, not required
```

Every current configuration document uses:

```json
{
    "version": 3
}
```

plus its domain-specific fields.

## Fail-closed validation

Current profile configuration is intentionally strict:

- a genuinely missing current-schema file may be created from the documented default structure;
- an existing file with malformed JSON is an error and is never treated as missing;
- an existing file with the wrong type, unsupported schema version, unknown key, or invalid nested value is an error;
- the complete current profile is validated before a processing workflow is allowed to use it.

This distinction is deliberate: defaults are bootstrap behavior for absent configuration, not a recovery path for configuration that exists but cannot be trusted.

## Ownership model

### `general/catalog.json`

Cross-workflow catalog vocabulary. Stock Processing and Cross Check consume these article/family labels at their workbook boundaries rather than assuming the demo names internally:

```json
{
    "version": 3,
    "columns": {
        "article": "Artículo",
        "family": "Familias"
    },
    "default_family": "Otro"
}
```

### `general/families.json`

Family → article-prefix rules:

```json
{
    "version": 3,
    "rules": {
        "Example Family": ["001", "01"],
        "REVISAR": ["REVISAR", "revisar"]
    }
}
```

Overlapping prefixes are valid. Longest-prefix matching is preserved by the shared classifier.

### `general/network.json`

Store/network structure:

```json
{
    "version": 3,
    "active": ["STORE_A", "STORE_B"],
    "regional_groups": {
        "REGION": ["STORE_A", "STORE_B"]
    },
    "stock_database_columns": {
        "STORE_A": "DS_STORE_A"
    }
}
```

### `stock_processing/settings.json`

Owns:

- cleaning text/numeric/drop-column rules;
- price-list column mapping/aliases;
- raw-data sheet name;
- base output columns;
- configured summary sheets/entities/titles.

This configuration belongs to Stock Processing; it must not be hidden in YoY configuration.

### `cross_check/settings.json`

Owns:

- ignored articles;
- ignored text terms;
- cost-list article/price columns;
- sales-list article/price columns.

### `yoy_reports/settings.json`

Owns:

- input date/quantity/sales-amount/family/article/branch/variant mapping;
- default output path;
- enabled metrics (`units` and/or `sales`) for direct engine calls; interactive CLI/GUI runs select units and explicitly opt into sales amounts for that run;
- annual-comparison/variant options;
- report groups that define the branches rendered by the workbook.

## `profile.json`

Human-facing profile metadata such as name/description/version. It is separate from processing schema version 3.

## Editing profiles

### Recommended: Configuration Hub

Open `K` in the CLI. The hub is domain-oriented and provides dedicated editors for Catalog/Families, Stores/Network, Stock Processing, Cross Check, and YoY.

### Guided Setup

The setup wizard uses module-specific sample files rather than assuming one spreadsheet contains columns for every workflow.

The readiness dashboard reports whether each domain has enough configuration to proceed.

### Direct JSON editing

Supported for maintainers and deployments that prefer source-controlled configuration. After editing:

```bash
python tools/ReleaseCheck.py
```

or validate from the CLI Configuration Hub.

## Creating a profile

The CLI can create/select profiles. The demo profile may also be used as a structural reference, but blindly copying its business values is not recommended.

A new profile's missing current-schema files are initialized from defaults without overwriting existing values.

## Last-path state

`last_paths.json` remembers previously selected files for convenience. It is local runtime state, not business configuration, and should not be treated as part of the schema-v3 contract.


## Versioning rule

Schema version is intentionally strict. A future schema change should include an explicit migration strategy or explicit failure; it should not silently treat an older version as current.

### Cross Check input and reconciliation policy

`cross_check/settings.json` owns `input.quantity_column` and
`reconciliation.ignore_negative_system_stock_when_counted`. Existing profiles
that omit these sections use the bundled defaults. Column preflight in the CLI
and GUI offers the same explicit default fallback as other configured columns.
With the policy enabled, counted articles with negative system stock use the
physical count as their difference. With it disabled, the difference is always
physical count minus system stock. Both values are editable in Config Hub.

### Price list article codes

`stock_processing/settings.json` stores `pricing.article_tokenization`.
`cross_check/settings.json` stores the same option under `pricing`. `first_token`
keeps the historical behavior, where text after the first whitespace is not part
of a price-list article code. `whole` keeps the entire cleaned code. Set this
option in each module's JSON if your SKUs can contain spaces; the two workflows
are configured independently. Existing profiles use `first_token` by default.

## Bundled defaults and profile ownership

`core/resources/profile_defaults.json` supplies missing-file bootstrap settings and default model values. Shared report vocabulary and discovery hints live in `workbook_labels.json` and `column_hints.json`. Profile JSON owns actual family prefixes, store/database mappings, exclusions, grouping and output settings. Changing a demo family must not require embedding that family in Python tests.

A configured input column that is absent requires explicit per-run consent in CLI/GUI before trying its bundled default. If the default is also absent, the run fails; unattended engine calls do not silently substitute columns. This fallback does not rewrite the stored profile.

## Copying profiles to another installation

1. Copy the complete `profiles/<name>/` folder into the destination installation's `profiles/` folder. Keep `profile.json` and the `configs/` layout intact; avoid overwriting an existing profile with the same name unintentionally.
2. Select the copied profile and validate it in Configuration Hub.
3. Copy or locate operational spreadsheets separately. The profile contains configuration, not those input workbooks.
4. Review or remove `last_paths.json` if paths belong to the old computer. Absolute remembered paths do not relocate automatically, including remembered demo selections. Removing this convenience file does not remove business configuration; demo suggestions then resolve under the new installation.

No import/export tool is needed for this folder layout. The destination must support the profile schema; current configuration headers remain strictly validated even after compatibility is retired.

### Guided setup lifecycle

New profiles record `setup.version = 1` and `setup.modules` in `profile.json`.
Each module keeps fingerprints for reviewed setup steps. The computed state is
0 (not configured), 1 (partial), or 2 (complete). Finishing a page saves it;
leaving the assistant keeps the saved pages. Unreviewed modules remain independent.
A shared-field change invalidates prior reviews of that field in other modules.
Existing profiles without this metadata retain their current validated behavior;
opening and saving a guided setup step enrolls that module in review tracking.
These states describe operator review, not proof that every future input file matches.

Stable errors expose a code, module, field and setup-step destination. Only
configuration errors with an explicit destination offer guided recovery. Missing
input columns continue to offer the existing per-run default fallback; they are
not interpreted as an unset configuration field.

When an existing profile enrolls one module, untouched modules carry a legacy marker and remain available under their previous lifecycle. Invalid setup metadata is rejected before configuration files are changed. Review states are derived from fingerprints rather than trusting a manually edited completion flag.

# Header advice in guided setup

The assistant can inspect a small Excel sample on each column-mapping page. It reports which configured headers exist and suggests a unique normalized or vocabulary match when possible. Ambiguous matches require a manual choice. Suggestions are never saved until the operator explicitly adopts them and saves the page. Matching vocabulary is stored in `core/resources/column_hints.json`, not in the matching algorithm.

## Optional variants

YoY `input.variant_column` identifies an optional product dimension, such as flavor, package weight or size. `output.include_variants` controls its default breakdown. The actual header is also used in report detail labels. A business with no variants leaves the breakdown off and does not need a variant column. Quantity remains a separate numeric measure: a presentation named "500 g" is a variant, while a sale of 1.25 kg is a quantity. Earlier `size_column` / `include_sizes` keys are accepted on read and become the generic names when saved.

## Enabled workflows

`profile.json` may contain `enabled_modules`, a nonempty list drawn from `cross_check`, `stock_processing` and `yoy_reports`. Missing selection means all workflows for existing profiles. Disabled workflows retain their configuration and setup progress; they do not need review before another workflow runs. Frontends and direct engine entry points reject disabled workflows. Configuration loading can target one module, so a malformed disabled module file does not block an enabled workflow. Shared catalog/family/network documents still belong to the profile.

## Module-owned input mappings

Catalog column names describe shared output vocabulary. Stock `input.article_column` and Cross Check `input.article_column` select independent input headers. Empty values inherit the earlier catalog mapping until setup is reviewed. Stock `input.quantity_columns` maps stable store identifiers to stock-file headers; `input.deposit_columns` maps optional additional quantities. An absent deposit map inherits the previous network mapping, while an explicit empty object disables deposits. Stock `pricing.cost_columns` and `sales_columns` independently override the earlier shared `columns` contract. Setup displays effective inherited values and saves explicit mappings on review. YoY retains its independent input mapping and report groups.

## Fractional quantities

Stock numeric cleaning preserves decimal quantities, including store/deposit columns. For weighted or volume-based goods, set Stock `output.quantity_label` (for example `kg`) and `output.quantity_format` (`#,##0.###`). YoY has the same format option and a report-block `quantity_label` such as `Quantity (kg)`. This is display configuration; quantity arithmetic uses the supplied values and never converts units. Do not combine incompatible units in a single quantity total.

## Conditional setup and shared reviews

The shared setup catalog defines labels, explanations, typed choices, numeric values, optional fields, sample-file roles and conditional pages. Normal setup reviews essential pages; additional configuration includes cleanup, filters, matching preferences, output layout and summaries. Scanner counts do not show quantity-table mappings; wide stock does not show row-based mappings. Unchanged shared settings reviewed in another module can be reused by a module that has not reviewed them yet. A module that already accepted older shared values must review a later change. Setup completion is review metadata, not proof that every row in a selected workbook is valid.

## Creating a profile

Both interfaces use `core.profile_creation.create_profile`. A display name generates a portable folder ID, workflows are selected before setup, and new profiles load `core/resources/new_profile_defaults.json` with neutral labels and whole-product identifiers instead of clothing/company defaults. Existing profile folders are never overwritten. A failed new-profile initialization removes only the new directory owned by that operation. The older bundled defaults continue to define inherited fields for existing schema-v3 profiles; they are not silently applied over an existing document.

## Categories and safe JSON writes

See [Category sources](CATEGORY_SOURCES.md) for source-column, prefix-rule and unclassified modes in Stock and Cross Check. Sales mappings remain independent.

JSON documents reject duplicate keys and non-finite numbers. Setup stages the configuration and review metadata together, replaces files atomically and restores the prior bytes if a later replacement fails. This prevents a failed save from keeping only one half of an edit; it is not a multi-process transaction or a guarantee against machine power loss between files. Keep one writer per profile.

Profile metadata must be a JSON object. Enabled workflows are a nonempty list of known names; remembered paths contain workflow objects with string paths. Invalid documents raise a configuration error and are not overwritten or treated as empty defaults.
