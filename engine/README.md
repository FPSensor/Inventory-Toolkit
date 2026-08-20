# Data Processing Engine

This directory contains the core analytical modules. It follows a decoupled design pattern where each domain is split into specific responsibilities.

## Structure
*   **`inventory_cross_check/`**: Handles physical vs. system stock reconciliation.
*   **`stock_processing/`**: Manages inventory valuation and dynamic summaries.
*   **`yoy_reports/`**: Generates historical Year-over-Year sales comparisons.
*   **`shared/`**: Common business rules, such as `families.py` for automated SKU classification.

## Internal Pattern
Each module is internally divided into:
1.  **`data_processor.py`**: Pure Pandas logic, mathematical calculations, and dataframe transformations.
2.  **`excel_renderer.py`**: OpenPyXL styling, formatting, and rendering.
3.  **`generator.py`**: The orchestrator that loads configs, calls the processor, and triggers the renderer.
