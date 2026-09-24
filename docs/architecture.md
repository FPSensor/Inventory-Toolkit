# 🏛️ Architectural Blueprint & Design Philosophy

## Why Decoupling Matters
In early versions of Inventory Toolkit, data logic and CLI interfaces were tightly intertwined. This created massive friction: changing how an Excel sheet was formatted risked breaking user inputs. 

In v1.2.0, we adopted a strict separation of concerns inspired by modern data engineering pipelines:
1. **Presentation Layer (`cli/`, experimental `gui/`)**: Gathers parameters and performs lightweight pre-flight validation. Some launchers inspect spreadsheet headers before invoking an engine.
2. **Business Logic Layer (`engine/`)**: Owns transformation, reconciliation, valuation, and report rendering. Engines can be called programmatically; save operations support a non-interactive mode for GUI callers.
3. **Infrastructure Layer (`core/`)**: Cross-cutting utilities such as logging, configuration validation, sanitization, and safe file handling.

## Design Choices & Trade-offs
* **Pandas vs. Pure SQL/ORM:** Retail inventory workflows heavily rely on legacy `.xls` and `.xlsx` exports from disparate local ERP systems. Pandas provides unmatched flexibility for handling messy, unstandardized table headers without requiring a running database server.
* **OpenPyXL Direct Manipulation:** Instead of generic Pandas Excel outputs, we use OpenPyXL to iterate over cells, apply custom hex fills (`#C6EFCE` for positive discrepancies, `#FFC7CE` for negative), draw thin gridlines, and force cell number formats (`#,##0.00`).
