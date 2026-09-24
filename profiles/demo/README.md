# Demo Profile

The `demo` profile is the checked-in reference configuration for Inventory Toolkit's bundled demo workbooks.

It demonstrates **configuration structure and workflow ownership**. It should not be copied as if its store names, families, or column mappings were universal business defaults.

## Structure

```text
demo/
├── profile.json
└── configs/
    ├── general/
    │   ├── catalog.json
    │   ├── families.json
    │   └── network.json
    ├── stock_processing/
    │   └── settings.json
    ├── cross_check/
    │   └── settings.json
    └── yoy_reports/
        └── settings.json
```

All current config files use schema version `3`.

## What each file demonstrates

- `general/catalog.json` — article/family column names and default family.
- `general/families.json` — longest-prefix family rules, including `REVISAR` handling.
- `general/network.json` — active stores, regional groups, and raw stock database-column mapping.
- `stock_processing/settings.json` — cleaning, pricing mapping/aliases, output/detail/summary layout.
- `cross_check/settings.json` — exclusions and cost/sales price-list mappings.
- `yoy_reports/settings.json` — historical input fields, output options, and reporting groups.

## Matching inputs

Use with files from:

```text
examples/demo/
```

## Creating your own profile

Recommended approach:

1. create/select the profile from Inventory Toolkit;
2. open `K` / Configuration;
3. run Guided Setup;
4. configure each module with a representative sample file;
5. validate the profile.

Maintainers may also duplicate the folder as a structural starting point, but business values must be reviewed rather than inherited blindly.

## Release role

The demo profile is fingerprinted together with `examples/demo/` by the release-reference manifest. Intentional changes may require reviewing and regenerating golden masters.

## Privacy

The reference profile intentionally avoids credentials, personal information, private contact data, and infrastructure secrets. If you create a real profile, review it before committing/sharing it.

See [`../../docs/profiles.md`](../../docs/profiles.md).
