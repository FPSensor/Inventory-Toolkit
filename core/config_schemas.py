"""Pydantic schemas for Inventory Toolkit profile configuration v2."""

from typing import Dict, List
from pydantic import BaseModel, ConfigDict, Field


class _Config(BaseModel):
    model_config = ConfigDict(extra="allow")
    version: int = 2


class CatalogColumns(BaseModel):
    article: str = "Artículo"
    family: str = "Familias"


class CatalogConfig(_Config):
    columns: CatalogColumns = Field(default_factory=CatalogColumns)
    default_family: str = "Otro"


class FamiliesConfig(_Config):
    rules: Dict[str, List[str]] = Field(default_factory=dict)


class StoresConfig(_Config):
    active: List[str] = Field(default_factory=list)
    regional_groups: Dict[str, List[str]] = Field(default_factory=dict)
    stock_database_columns: Dict[str, str] = Field(default_factory=dict)


class CleaningConfig(BaseModel):
    text_columns: List[str] = Field(default_factory=list)
    drop_columns: List[str] = Field(default_factory=list)
    numeric_columns: List[str] = Field(default_factory=list)


class PricingColumns(BaseModel):
    article: str = "Artículo"
    database: str = "Origen - Base de datos"
    price: str = "Precio"


class PricingConfig(BaseModel):
    columns: PricingColumns = Field(default_factory=PricingColumns)
    aliases: Dict[str, str] = Field(default_factory=dict)


class StockOutputConfig(BaseModel):
    raw_data_sheet: str = "Datos"
    base_columns: List[str] = Field(default_factory=lambda: ["Artículo", "Familias"])
    summaries: List[dict] = Field(default_factory=list)


class StockProcessingConfig(_Config):
    cleaning: CleaningConfig = Field(default_factory=CleaningConfig)
    pricing: PricingConfig = Field(default_factory=PricingConfig)
    output: StockOutputConfig = Field(default_factory=StockOutputConfig)


class CrossCheckFilters(BaseModel):
    ignored_articles: List[str] = Field(default_factory=list)
    ignored_terms: List[str] = Field(default_factory=list)


class PriceListColumns(BaseModel):
    article_column: str = "Artículo"
    price_column: str = "Precio"


class CrossCheckPriceLists(BaseModel):
    cost: PriceListColumns = Field(default_factory=PriceListColumns)
    sales: PriceListColumns = Field(default_factory=PriceListColumns)


class CrossCheckConfig(_Config):
    filters: CrossCheckFilters = Field(default_factory=CrossCheckFilters)
    price_lists: CrossCheckPriceLists = Field(default_factory=CrossCheckPriceLists)


class YoYInputConfig(BaseModel):
    date_column: str = "Fecha"
    quantity_column: str = "Cantidad"
    grouping_column: str = "Familias"
    item_column: str = "Articulo"
    branch_column: str = "Base"
    size_column: str = "Talle"


class YoYOutputConfig(BaseModel):
    default_path: str = "analysis_report.xlsx"
    metrics: List[str] = Field(default_factory=lambda: ["unidades", "ventas"])
    annual_comparison: bool = True
    include_sizes: bool = False


class YoYReportsConfig(_Config):
    input: YoYInputConfig = Field(default_factory=YoYInputConfig)
    output: YoYOutputConfig = Field(default_factory=YoYOutputConfig)
    groups: Dict[str, List[str]] = Field(default_factory=dict)
