"""Pydantic schemas for Inventory Toolkit profile configuration."""

from typing import Dict, List, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.profile_config import CONFIG_VERSION

from core.business_schema import (
    ARTICLE_COLUMN,
    DATABASE_ORIGIN_COLUMN,
    DEFAULT_FAMILY,
    FAMILY_COLUMN,
    PRICE_COLUMN,
    QUANTITY_COLUMN,
    RAW_DATA_SHEET,
    SIZE_COLUMN,
)


class _StrictConfigModel(BaseModel):
    """Reject unknown configuration keys instead of silently ignoring typos."""

    model_config = ConfigDict(extra="forbid")


class _Config(_StrictConfigModel):
    version: Literal[CONFIG_VERSION]


class CatalogColumns(_StrictConfigModel):
    article: str = ARTICLE_COLUMN
    family: str = FAMILY_COLUMN


class CatalogConfig(_Config):
    columns: CatalogColumns = Field(default_factory=CatalogColumns)
    default_family: str = DEFAULT_FAMILY

    @field_validator("default_family")
    @classmethod
    def validate_default_family(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("default_family cannot be empty")
        return normalized


class FamiliesConfig(_Config):
    rules: Dict[str, List[str]] = Field(default_factory=dict)


class NetworkConfig(_Config):
    active: List[str] = Field(default_factory=list)
    regional_groups: Dict[str, List[str]] = Field(default_factory=dict)
    stock_database_columns: Dict[str, str] = Field(default_factory=dict)


class CleaningConfig(_StrictConfigModel):
    text_columns: List[str] = Field(default_factory=list)
    drop_columns: List[str] = Field(default_factory=list)
    numeric_columns: List[str] = Field(default_factory=list)


class PricingColumns(_StrictConfigModel):
    article: str = ARTICLE_COLUMN
    database: str = DATABASE_ORIGIN_COLUMN
    price: str = PRICE_COLUMN


class PricingConfig(_StrictConfigModel):
    columns: PricingColumns = Field(default_factory=PricingColumns)
    aliases: Dict[str, str] = Field(default_factory=dict)


class StockSummaryConfig(_StrictConfigModel):
    sheet_name: str = "Summary"
    entities: List[str] = Field(default_factory=list)
    titles: List[str] = Field(default_factory=list)


class StockOutputConfig(_StrictConfigModel):
    raw_data_sheet: str = RAW_DATA_SHEET
    base_columns: List[str] = Field(default_factory=lambda: [ARTICLE_COLUMN, FAMILY_COLUMN])
    summaries: List[StockSummaryConfig] = Field(default_factory=list)


class StockProcessingConfig(_Config):
    cleaning: CleaningConfig = Field(default_factory=CleaningConfig)
    pricing: PricingConfig = Field(default_factory=PricingConfig)
    output: StockOutputConfig = Field(default_factory=StockOutputConfig)


class CrossCheckFilters(_StrictConfigModel):
    ignored_articles: List[str] = Field(default_factory=list)
    ignored_terms: List[str] = Field(default_factory=list)


class PriceListColumns(_StrictConfigModel):
    article_column: str = ARTICLE_COLUMN
    price_column: str = PRICE_COLUMN


class CrossCheckPriceLists(_StrictConfigModel):
    cost: PriceListColumns = Field(default_factory=PriceListColumns)
    sales: PriceListColumns = Field(default_factory=PriceListColumns)


class CrossCheckConfig(_Config):
    filters: CrossCheckFilters = Field(default_factory=CrossCheckFilters)
    price_lists: CrossCheckPriceLists = Field(default_factory=CrossCheckPriceLists)


class YoYInputConfig(_StrictConfigModel):
    date_column: str = "Fecha"
    quantity_column: str = QUANTITY_COLUMN
    sales_column: str = "Monto"
    grouping_column: str = FAMILY_COLUMN
    item_column: str = "Articulo"
    branch_column: str = "Base"
    size_column: str = SIZE_COLUMN


class YoYOutputConfig(_StrictConfigModel):
    default_path: str = "analysis_report.xlsx"
    metrics: List[Literal["units", "sales"]] = Field(
        default_factory=lambda: ["units", "sales"],
        min_length=1,
    )
    annual_comparison: bool = True
    include_sizes: bool = False


class YoYReportsConfig(_Config):
    input: YoYInputConfig = Field(default_factory=YoYInputConfig)
    output: YoYOutputConfig = Field(default_factory=YoYOutputConfig)
    groups: Dict[str, List[str]] = Field(default_factory=dict)
