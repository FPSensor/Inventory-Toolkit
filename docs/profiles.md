# 👤 Profiles & Configuration v3 (`/profiles`)

Profiles keep business rules outside the engines, so the same Inventory Toolkit build can serve different companies, datasets, or test environments without hard-coded forks.

## Configuration tree

Each profile now uses a **module-oriented v3 layout**:

```text
profiles/<name>/
├── profile.json
├── configs/
│   ├── general/
│   │   ├── catalog.json       # core article/family columns and fallback family
│   │   ├── families.json      # family → SKU-prefix rules
│   │   └── network.json       # active stores, regional groups, raw DB columns
│   ├── stock_processing/
│   │   └── settings.json      # cleaning, pricing input, Stock output layout
│   ├── cross_check/
│   │   └── settings.json      # exclusions and cost/sales price-list columns
│   └── yoy_reports/
│       └── settings.json      # YoY input mapping, output options, report groups
└── last_paths.json
```

The important rule is **ownership**: Stock Processing settings live under Stock Processing; YoY settings live under YoY. The old `yoy_reports/reports.json` mixed Stock output layout and YoY configuration in one file and has been removed from the modular schema.

## Editing configuration

For normal use, prefer **Configuration Hub** or the **Guided Setup**. The JSON files remain intentionally readable and version-control friendly, but users should not need to understand the filesystem layout just to configure a profile.

The Guided Setup is module-oriented rather than a fixed eight-step sequence. Each workflow can use the Excel sample that actually belongs to it:

- Stock Processing can inspect a raw stock file and a separate price-list sample.
- Cross Check can inspect its own Cost and Sales list samples.
- YoY can inspect the historical sales file.
- Catalog and Network can be configured independently.

Progress is saved after each module, and the setup dashboard shows which modules are ready.

<!-- BEGIN LEGACY_COMPATIBILITY -->
## Legacy v1 migration

`ConfigurationManager` can read a legacy profile and create equivalent current-schema files automatically. Configuration Hub also provides **Migrate/archive legacy config**, which moves the old JSON files to:

```text
configs/_legacy_v1_backup/
```

Legacy v1 and v2 keys are decoded only at the migration boundary. Built-in engines use the native English configuration API; migration changes storage and implementation vocabulary, not business behavior.
<!-- END LEGACY_COMPATIBILITY -->
