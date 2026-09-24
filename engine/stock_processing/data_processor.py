"""Data transformations shared by the Stock Processing workflow."""

import os

import numpy as np
import pandas as pd

from core.business_schema import ARTICLE_COLUMN
from core.logger import log

_ARTICLE_FALLBACKS = [ARTICLE_COLUMN, "Articulo", "SKU", "Codigo", "Item"]
_DATABASE_FALLBACKS = ["Origen - Base de datos", "Sucursal", "Base", "Local", "Origen", "Tienda"]
_VALUE_FALLBACKS = ["Precio", "Costo", "Venta", "Valor", "Monto"]
_NON_VALUE_COLUMNS = {"Talle", "Color"}
_NON_VALUE_CODES = {"EAN", "ID", "COD", "CÓDIGO", "CODIGO", "BARCODE"}


def _first_existing(columns, candidates):
    return next((candidate for candidate in candidates if candidate in columns), None)


def process_pricing(file_path, pricing_config=None):
    """Load and pivot a price list while preserving the historical fallbacks."""
    if not file_path or not os.path.exists(file_path):
        return None

    try:
        dataframe = pd.read_excel(file_path)
        pricing_config = pricing_config or {}
        configured_columns = pricing_config.get("columns", {})

        article_candidates = [configured_columns.get("article")] + _ARTICLE_FALLBACKS
        article_column = _first_existing(
            dataframe.columns,
            [candidate for candidate in article_candidates if candidate],
        )
        if not article_column:
            log.warning("Article column not found in %s.", file_path)
            return None

        dataframe[ARTICLE_COLUMN] = dataframe[article_column].astype(str).str.split(" ").str[0]

        aliases = pricing_config.get("aliases", {})
        database_candidates = [configured_columns.get("database"), *aliases.keys(), *_DATABASE_FALLBACKS]
        database_column = _first_existing(
            dataframe.columns,
            [candidate for candidate in database_candidates if candidate],
        )
        if not database_column:
            database_column = "Base_General"
            dataframe[database_column] = "General"

        value_candidates = [configured_columns.get("price"), *_VALUE_FALLBACKS]
        value_column = _first_existing(
            dataframe.columns,
            [candidate for candidate in value_candidates if candidate],
        )
        if not value_column:
            numeric_columns = dataframe.select_dtypes(include="number").columns.tolist()
            available_columns = [
                column
                for column in numeric_columns
                if column not in [article_column, database_column, *_NON_VALUE_COLUMNS]
                and str(column).upper() not in _NON_VALUE_CODES
            ]
            if not available_columns:
                log.warning("Value column not found in %s.", file_path)
                return None
            value_column = available_columns[-1]

        pivot = pd.pivot_table(
            dataframe,
            index=ARTICLE_COLUMN,
            columns=database_column,
            values=value_column,
            aggfunc="mean",
        ).reset_index()
        pivot.columns.name = None
        return pivot
    except Exception as exc:
        log.error("Processing %s: %s", file_path, exc)
        return None


def calculate_margin(dataframe, sales_column, cost_column):
    return np.where(
        dataframe[sales_column] > 0,
        (dataframe[sales_column] - dataframe[cost_column]) / dataframe[sales_column],
        0,
    )
