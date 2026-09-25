"""Price-list ingestion and normalization for Stock Processing."""

from __future__ import annotations

import os

import pandas as pd

from core.business_schema import ARTICLE_COLUMN
from core.logger import log, log_debug_event, log_exception
from engine.stock_processing.contracts import INTERNAL_ARTICLE_COLUMN

_ARTICLE_FALLBACKS = [ARTICLE_COLUMN, "Articulo", "SKU", "Codigo", "Item"]
_DATABASE_FALLBACKS = ["Origen - Base de datos", "Sucursal", "Base", "Local", "Origen", "Tienda"]
_VALUE_FALLBACKS = ["Precio", "Costo", "Venta", "Valor", "Monto"]
_NON_VALUE_COLUMNS = {"Talle", "Color"}
_NON_VALUE_CODES = {"EAN", "ID", "COD", "CÓDIGO", "CODIGO", "BARCODE"}


def _first_existing(columns, candidates):
    return next((candidate for candidate in candidates if candidate in columns), None)


def _resolve_pricing_columns(dataframe: pd.DataFrame, pricing_config: dict) -> tuple[str, str, str]:
    """Resolve the historical price-list contract in one isolated place.

    Current configured names have priority.  Historical fallbacks are retained
    deliberately for v1.x compatibility, rather than being scattered through
    the valuation pipeline.
    """
    configured = pricing_config.get("columns", {})

    article_candidates = [configured.get("article"), *_ARTICLE_FALLBACKS]
    article_column = _first_existing(
        dataframe.columns,
        [candidate for candidate in article_candidates if candidate],
    )
    if not article_column:
        raise ValueError("Article column not found in price list.")

    aliases = pricing_config.get("aliases", {})
    database_candidates = [configured.get("database"), *aliases.keys(), *_DATABASE_FALLBACKS]
    database_column = _first_existing(
        dataframe.columns,
        [candidate for candidate in database_candidates if candidate],
    )
    if not database_column:
        database_column = "Base_General"
        dataframe[database_column] = "General"

    value_candidates = [configured.get("price"), *_VALUE_FALLBACKS]
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
            raise ValueError("Value column not found in price list.")
        value_column = available_columns[-1]

    return article_column, database_column, value_column


def process_pricing(file_path, pricing_config=None):
    """Load and pivot one price list into the Stock pipeline's private article key."""
    if not file_path or not os.path.exists(file_path):
        log_debug_event("pricing_skipped", file_path=file_path, reason="missing_file")
        return None

    try:
        dataframe = pd.read_excel(file_path)
        log_debug_event(
            "pricing_loaded",
            file_path=file_path,
            shape=dataframe.shape,
            columns=list(dataframe.columns),
        )
        pricing_config = pricing_config or {}
        article_column, database_column, value_column = _resolve_pricing_columns(
            dataframe,
            pricing_config,
        )

        dataframe[INTERNAL_ARTICLE_COLUMN] = (
            dataframe[article_column].astype(str).str.split(" ").str[0]
        )
        log_debug_event(
            "pricing_columns_resolved",
            file_path=file_path,
            article_column=article_column,
            database_column=database_column,
            value_column=value_column,
        )
        pivot = pd.pivot_table(
            dataframe,
            index=INTERNAL_ARTICLE_COLUMN,
            columns=database_column,
            values=value_column,
            aggfunc="mean",
        ).reset_index()
        pivot.columns.name = None
        log_debug_event(
            "pricing_pivot_ready",
            file_path=file_path,
            shape=pivot.shape,
            columns=list(pivot.columns),
        )
        return pivot
    except Exception as exc:
        log_exception("Processing %s: %s", file_path, exc)
        return None
