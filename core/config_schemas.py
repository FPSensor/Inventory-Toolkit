"""Pydantic schemas for Inventory Toolkit profile configuration."""

from typing import Dict, List

from pydantic import BaseModel, ConfigDict, Field

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


class _Config(BaseModel):
    model_config = ConfigDict(extra="allow")
    version: int = 3


class CatalogColumns(BaseModel):
    article: str = ARTICLE_COLUMN
    family: str = FAMILY_COLUMN


class CatalogConfig(_Config):
    columns: CatalogColumns = Field(default_factory=CatalogColumns)
    default_family: str = DEFAULT_FAMILY


class FamiliesConfig(_Config):
    rules: Dict[str, List[str]] = Field(default_factory=dict)


class NetworkConfig(_Config):
    active: List[str] = Field(default_factory=list)
    regional_groups: Dict[str, List[str]] = Field(default_factory=dict)
    stock_database_columns: Dict[str, str] = Field(default_factory=dict)


class CleaningConfig(BaseModel):
    text_columns: List[str] = Field(default_factory=list)
    drop_columns: List[str] = Field(default_factory=list)
    numeric_columns: List[str] = Field(default_factory=list)


class PricingColumns(BaseModel):
    article: str = ARTICLE_COLUMN
    database: str = DATABASE_ORIGIN_COLUMN
    price: str = PRICE_COLUMN


class PricingConfig(BaseModel):
    columns: PricingColumns = Field(default_factory=PricingColumns)
    aliases: Dict[str, str] = Field(default_factory=dict)


class StockSummaryConfig(BaseModel):
    sheet_name: str = "Summary"
    entities: List[str] = Field(default_factory=list)
    titles: List[str] = Field(default_factory=list)


class StockOutputConfig(BaseModel):
    raw_data_sheet: str = RAW_DATA_SHEET
    base_columns: List[str] = Field(default_factory=lambda: [ARTICLE_COLUMN, FAMILY_COLUMN])
    summaries: List[StockSummaryConfig] = Field(default_factory=list)


class StockProcessingConfig(_Config):
    cleaning: CleaningConfig = Field(default_factory=CleaningConfig)
    pricing: PricingConfig = Field(default_factory=PricingConfig)
    output: StockOutputConfig = Field(default_factory=StockOutputConfig)


class CrossCheckFilters(BaseModel):
    ignored_articles: List[str] = Field(default_factory=list)
    ignored_terms: List[str] = Field(default_factory=list)


class PriceListColumns(BaseModel):
    article_column: str = ARTICLE_COLUMN
    price_column: str = PRICE_COLUMN


class CrossCheckPriceLists(BaseModel):
    cost: PriceListColumns = Field(default_factory=PriceListColumns)
    sales: PriceListColumns = Field(default_factory=PriceListColumns)


class CrossCheckConfig(_Config):
    filters: CrossCheckFilters = Field(default_factory=CrossCheckFilters)
    price_lists: CrossCheckPriceLists = Field(default_factory=CrossCheckPriceLists)


class YoYInputConfig(BaseModel):
    date_column: str = "Fecha"
    quantity_column: str = QUANTITY_COLUMN
    grouping_column: str = FAMILY_COLUMN
    item_column: str = "Articulo"
    branch_column: str = "Base"
    size_column: str = SIZE_COLUMN


class YoYOutputConfig(BaseModel):
    default_path: str = "analysis_report.xlsx"
    metrics: List[str] = Field(default_factory=lambda: ["units", "sales"])
    annual_comparison: bool = True
    include_sizes: bool = False


class YoYReportsConfig(_Config):
    input: YoYInputConfig = Field(default_factory=YoYInputConfig)
    output: YoYOutputConfig = Field(default_factory=YoYOutputConfig)
    groups: Dict[str, List[str]] = Field(default_factory=dict)
