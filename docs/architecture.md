# 🏛️ Architectural Blueprint & Design Philosophy

## Why Decoupling Matters
In early versions of Inventory Toolkit, data logic and CLI interfaces were tightly intertwined. This created massive friction: changing how an Excel sheet was formatted risked breaking user inputs. 

In v1.3.1, we adopted a strict separation of concerns inspired by modern data engineering pipelines:
1. **Presentation Layer (`cli/`)**: Never touches dataframes directly; only gathers parameters and validates input presence.
2. **Business Logic Layer (`engine/`)**: Pure computational and rendering engines. Completely headless. Can be executed programmatically via custom Python scripts without a terminal.
3. **Infrastructure Layer (`core/`)**: Cross-cutting utilities (logging, system safety bounds, configuration managers).

## Design Choices & Trade-offs
* **Pandas vs. Pure SQL/ORM:** Retail inventory workflows heavily rely on legacy `.xls` and `.xlsx` exports from disparate local ERP systems. Pandas provides unmatched flexibility for handling messy, unstandardized table headers without requiring a running database server.
* **OpenPyXL Direct Manipulation:** Instead of generic Pandas Excel outputs, we use OpenPyXL to iterate over cells, apply custom hex fills (`#C6EFCE` for positive discrepancies, `#FFC7CE` for negative), draw thin gridlines, and force cell number formats (`#,##0.00`).
