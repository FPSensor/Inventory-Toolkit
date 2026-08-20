# 👤 Profiles & Configurations (`/profiles`)

Profiles allow the exact same codebase to serve multiple retail clients or branches simultaneously without cross-contaminating datasets.

## Structure Inside `profiles/<name>/`
* `profile.json`: Metadata, profile description, and sample file pointers.
* `configs/general/`: Shared definitions (`familias.json`, `stores.json`, `databases.json`, `schema.json`, `settings.json`).
* `configs/cross_check/`: Specific rules for reconciliation (`cross_check_settings.json`).
* `configs/stock_processing/`: Cleaning rules and pricing schemas (`cleaning.json`, `pricing.json`).
* `configs/yoy_reports/`: Time-series and layout structures (`reports.json`).
