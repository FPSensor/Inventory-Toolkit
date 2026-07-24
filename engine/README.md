# Engine

The `engine` package contains the core processing algorithms used by Inventory Toolkit.

Unlike the CLI, the engine is completely independent from user interaction.

Its only responsibility is to transform input data into processed Excel files.

---

## Current Modules

| Module | Description |
|---------|-------------|
| Stocks.py | Stock Processing |
| Cruces.py | Inventory Reconciliation |

---

## Responsibilities

- Read Excel files
- Apply business rules
- Process inventory
- Generate reports
- Export results

---

## Design Goals

The engine should remain:

- independent
- reusable
- deterministic

No module inside `engine` should request user input.

Configuration is provided externally through the selected profile.

---

## Configuration

Business rules are loaded from

```
profiles/<profile>/configs/
```

This allows the same engine to work with completely different companies without modifying the source code.

---

## Future

The long-term objective is to completely isolate processing logic from configuration loading, allowing Inventory Toolkit to support additional interfaces beyond the CLI.