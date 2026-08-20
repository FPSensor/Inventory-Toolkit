# 🧪 Testing Suite & Demo Datasets

## Automated Tests (`/tests`)
We use `pytest` to guarantee mathematical and structural integrity. 
* `test_inventory_cross_check.py`: Validates sorting algorithms for prefix priority and difference calculations (handling negative system stocks correctly).
* `test_stock_processing.py`: Validates margin formulas and fallback zero-handling.

## Demo Dataset (`/examples/demo`)
Sanitized, structure-preserving mock spreadsheets designed to let users test all three core modules out of the box without real corporate data exposure.
