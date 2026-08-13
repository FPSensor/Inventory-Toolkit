# Engine

The `engine` package contains the core processing algorithms used by Inventory Toolkit[cite: 4].

Unlike the CLI, the engine is completely independent from user interaction[cite: 4].

Its only responsibility is to transform input data into processed Excel files[cite: 4].

---

## Current Modules

| Module | Description |
|---------|-------------|
| Stocks.py | Stock Processing[cite: 4] |
| Cruces.py | Inventory Reconciliation[cite: 4] |
| reports/ | Year-over-Year (YoY) Sales Analysis and Excel Generation |

---

## Responsibilities

- Read Excel files[cite: 4]
- Apply business rules[cite: 4]
- Process inventory and sales[cite: 4]
- Generate reports[cite: 4]
- Export results[cite: 4]

---

## Design Goals

The engine should remain:

- independent[cite: 4]
- reusable[cite: 4]
- deterministic[cite: 4]

No module inside `engine` should request user input[cite: 4].

Configuration is provided externally through the selected profile[cite: 4].

---

## Configuration

Business rules are loaded from

profiles//configs/


This allows the same engine to work with completely different companies without modifying the source code[cite: 4].

---

## Roaddmap

- Improve logging