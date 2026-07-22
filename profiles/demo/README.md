# Inventory Toolkit - Example Profile

This repository contains the default example profile for **Inventory Toolkit**.

Its purpose is to demonstrate how Inventory Toolkit is configured without exposing any private business information.

## What is included?

- Example configuration files
- Family mapping
- Database mapping
- Report settings
- Cleaning rules
- Store definitions

This profile is intended to serve as a reference when creating new profiles for different companies or inventory systems.

## Directory Structure

```
profiles/
└── example/
    ├── configs/
    │   ├── cleaning.json
    │   ├── databases.json
    │   ├── familias.json
    │   ├── pricing.json
    │   ├── reports.json
    │   └── stores.json
    └── README.md
```

## Creating your own profile

1. Copy the `example` profile.

```
profiles/
└── my_company/
```

2. Modify the JSON files to match your environment.

3. Select the profile from Inventory Toolkit (future CLI support).

## Important

The example profile intentionally does **not** include:

- Real inventory data
- Price lists
- Company reports
- Production spreadsheets

Only the configuration required to understand the project architecture is provided.

## License

Same license as Inventory Toolkit.