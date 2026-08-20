# 🧠 Engine Subsystems Reference (`/engine`)

Every subdirectory inside `/engine` follows the strict **Data Processor / Excel Renderer / Generator** triad.

## 1. Inventory Cross Check (`inventory_cross_check/`)
* **Problem:** Physical barcode scans often contain truncated codes, typos, or missing system prefixes.
* **Solution:** Master database index mapping with longest-prefix sorting (`data_processor.py`). Matches are dynamically cleaned and categorized.

## 2. Stock Processing (`stock_processing/`)
* **Problem:** Multi-branch inventories need valuation across separate cost and pricing lists, plus regional group roll-ups.
* **Solution:** Dynamic pivoting, automatic column typecasting (comma-to-dot float conversions), and safe margin arithmetic that protects against `DivisionByZero`.

## 3. YoY Sales Reports (`yoy_reports/`)
* **Problem:** Comparing historical performance across time periods with fluctuating structures.
* **Solution:** Date offset calculations (`pd.DateOffset(years=1)`), automatic family generation via `shared/families.py`, and multi-sheet workbook generation (monthly segmented or full year summaries).
