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

This distinction is deliberate: defaults are bootstrap behavior for absent configuration, not a recovery path for configuration that exists but cannot be trusted. Supported pre-v3 storage is converted by the compatibility layer before strict current-schema validation.

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

- input date/quantity/sales-amount/family/article/branch/size mapping;
- default output path;
- enabled metrics (`units` and/or `sales`);
- annual-comparison/size options;
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

<!-- BEGIN LEGACY_COMPATIBILITY -->
## Legacy profile migration

Inventory Toolkit temporarily recognizes pre-v3 storage and old serialized Spanish keys.

Configuration Hub exposes a migration/archive path. Legacy JSON is converted to the current modular schema and archived under:

```text
configs/_legacy_v1_backup/
```

Current built-in engines use native schema-v3 accessors after migration.

Debug level 2/3 reports compatibility usage so maintainers can identify remaining callers/profiles. See [legacy_compatibility.md](legacy_compatibility.md).
<!-- END LEGACY_COMPATIBILITY -->

## Versioning rule

Schema version is intentionally strict. A future schema change should include an explicit migration strategy or explicit failure; it should not silently treat an older version as current.
