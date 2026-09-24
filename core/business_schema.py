"""Business-facing workbook labels used by Inventory Toolkit.

These strings are intentionally not translated as part of the internal English
codebase cleanup. They are part of the current retail workflow, input files, or
exported workbook contract. Keeping them centralized makes that boundary
explicit: Python identifiers and configuration structure are English, while
business data remains faithful to the source systems.
"""

ARTICLE_COLUMN = "Artículo"
FAMILY_COLUMN = "Familias"
QUANTITY_COLUMN = "Cantidad"
SIZE_COLUMN = "Talle"
PRICE_COLUMN = "Precio"
COST_COLUMN = "Costo"
SALES_VALUE_LABEL = "Venta"
DATABASE_ORIGIN_COLUMN = "Origen - Base de datos"
RAW_DATA_SHEET = "Datos"
DEFAULT_FAMILY = "Otro"

SYSTEM_STOCK_COLUMN = "Stock Sistema"
PHYSICAL_COUNT_COLUMN = "Conteo Físico"
DIFFERENCE_COLUMN = "Diferencia"
COST_TOTAL_COLUMN = "CTOTAL"
SALES_TOTAL_COLUMN = "VTOTAL"

REVIEW_FAMILY = "REVISAR"
REVIEW_PREFIX = "REVISAR | "

UNIT_COST_PREFIX = "PrecioUnit.Costo."
UNIT_SALES_PREFIX = "PrecioUnit.Venta."
MARGIN_PREFIX = "Margen_"
