"""Pydantic schemas for Inventory Toolkit profile configuration."""

from typing import Dict, List, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core.profile_config import CONFIG_VERSION, DEFAULTS
from core.system_utils import normalize_xlsx_output_path

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

    @field_validator("article", "family")
    @classmethod
    def validate_catalog_column_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("catalog column names cannot be empty")
        return normalized

    @model_validator(mode="after")
    def validate_distinct_catalog_columns(self):
        if self.article == self.family:
            raise ValueError("catalog article and family columns must use different names")
        return self


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
    article_tokenization: Literal["first_token", "whole"] = "first_token"
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


class CrossCheckInput(_StrictConfigModel):
    quantity_column: str = DEFAULTS["cross_check/settings"]["input"]["quantity_column"]

    @field_validator("quantity_column")
    @classmethod
    def validate_quantity_column(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("cross-check quantity column cannot be empty")
        return value


class CrossCheckReconciliation(_StrictConfigModel):
    ignore_negative_system_stock_when_counted: bool = DEFAULTS[
        "cross_check/settings"
    ]["reconciliation"]["ignore_negative_system_stock_when_counted"]


class PriceArticleRules(_StrictConfigModel):
    article_tokenization: Literal["first_token", "whole"] = "first_token"


class CrossCheckConfig(_Config):
    pricing: PriceArticleRules = Field(default_factory=PriceArticleRules)
    input: CrossCheckInput = Field(default_factory=CrossCheckInput)
    reconciliation: CrossCheckReconciliation = Field(default_factory=CrossCheckReconciliation)
    filters: CrossCheckFilters = Field(default_factory=CrossCheckFilters)
    price_lists: CrossCheckPriceLists = Field(default_factory=CrossCheckPriceLists)


class YoYInputConfig(_StrictConfigModel):
    date_column: str = DEFAULTS["yoy_reports/settings"]["input"]["date_column"]
    quantity_column: str = QUANTITY_COLUMN
    sales_column: str = DEFAULTS["yoy_reports/settings"]["input"]["sales_column"]
    grouping_column: str = FAMILY_COLUMN
    item_column: str = DEFAULTS["yoy_reports/settings"]["input"]["item_column"]
    branch_column: str = DEFAULTS["yoy_reports/settings"]["input"]["branch_column"]
    size_column: str = SIZE_COLUMN


class YoYOutputConfig(_StrictConfigModel):
    default_path: str = "analysis_report.xlsx"

    @field_validator("default_path")
    @classmethod
    def validate_default_output_path(cls, value: str) -> str:
        return normalize_xlsx_output_path(value)
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
