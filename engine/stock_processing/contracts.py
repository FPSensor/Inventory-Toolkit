"""Resolved contracts for the Stock Processing pipeline.

The raw workbooks are allowed to use profile-owned business column names.  The
pipeline converts the two cross-workflow catalog columns (article/family) to
private internal keys while processing so the engine never mixes configurable
external vocabulary with implementation details.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from core.business_schema import ARTICLE_COLUMN, FAMILY_COLUMN, RAW_DATA_SHEET
from core.configuration_manager import ConfigurationManager

INTERNAL_ARTICLE_COLUMN = "__itk_article"
INTERNAL_FAMILY_COLUMN = "__itk_family"


@dataclass(frozen=True)
class StockProcessingPlan:
    """Fully resolved profile contract consumed by Stock Processing."""

    article_column: str
    family_column: str
    default_family: str
    family_rules: Mapping[str, list[str]]
    active_stores: tuple[str, ...]
    regional_groups: Mapping[str, tuple[str, ...]]
    stock_database_columns: Mapping[str, str]
    text_columns: tuple[str, ...]
    numeric_columns: tuple[str, ...]
    drop_columns: tuple[str, ...]
    pricing: Mapping[str, Any]
    base_columns: tuple[str, ...]
    raw_data_sheet: str
    summaries: tuple[Mapping[str, Any], ...]

    @classmethod
    def from_manager(cls, config: ConfigurationManager) -> "StockProcessingPlan":
        catalog = config.get_catalog()
        network = config.get_network_config()
        stock = config.get_stock_processing_config()

        catalog_columns = catalog["columns"]
        cleaning = stock["cleaning"]
        output = stock["output"]

        article_column = str(catalog_columns["article"]).strip()
        family_column = str(catalog_columns["family"]).strip()
        if not article_column:
            raise ValueError("Stock Processing requires a non-empty catalog article column.")
        if not family_column:
            raise ValueError("Stock Processing requires a non-empty catalog family column.")
        if article_column == family_column:
            raise ValueError(
                "Stock Processing catalog article and family columns must use different names."
            )

        return cls(
            article_column=article_column,
            family_column=family_column,
            default_family=catalog["default_family"],
            family_rules=config.get_family_rules(),
            active_stores=tuple(network["active"]),
            regional_groups={
                name: tuple(branches)
                for name, branches in network["regional_groups"].items()
            },
            stock_database_columns=dict(network["stock_database_columns"]),
            text_columns=tuple(cleaning.get("text_columns", [])),
            numeric_columns=tuple(cleaning.get("numeric_columns", [])),
            drop_columns=tuple(cleaning.get("drop_columns", [])),
            pricing=stock["pricing"],
            base_columns=tuple(
                output.get("base_columns", [ARTICLE_COLUMN, FAMILY_COLUMN])
            ),
            raw_data_sheet=output.get("raw_data_sheet", RAW_DATA_SHEET),
            summaries=tuple(output.get("summaries", [])),
        )

    @property
    def entities_to_value(self) -> tuple[str, ...]:
        return (*self.active_stores, *self.regional_groups.keys())

    def internal_base_column(self, configured_name: str) -> str:
        """Resolve a configured output label to the pipeline's internal key.

        The canonical v1.x labels remain accepted as aliases so a profile that
        changes catalog vocabulary does not also have to rewrite an untouched
        historical ``output.base_columns`` list just to keep article/family in
        the report.
        """
        if configured_name in {self.article_column, ARTICLE_COLUMN}:
            return INTERNAL_ARTICLE_COLUMN
        if configured_name in {self.family_column, FAMILY_COLUMN}:
            return INTERNAL_FAMILY_COLUMN
        return configured_name

    def expose_catalog_columns(self, dataframe):
        """Return a copy with private article/family keys restored to profile labels."""
        rename_map = {
            INTERNAL_ARTICLE_COLUMN: self.article_column,
            INTERNAL_FAMILY_COLUMN: self.family_column,
        }
        return dataframe.rename(
            columns={key: value for key, value in rename_map.items() if key in dataframe.columns}
        )
