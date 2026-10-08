"""Presentation-neutral guided setup steps; labels never expose storage keys."""
from dataclasses import dataclass


@dataclass(frozen=True)
class SetupField:
    path: tuple[str, ...]
    label: str
    help: str
    kind: str = 'column'


@dataclass(frozen=True)
class SetupStep:
    id: str
    title: str
    logical: str
    fields: tuple[SetupField, ...]
    shared: bool = False


def field(path, label, help, kind='column'):
    return SetupField(tuple(path.split('.')), label, help, kind)


ARTICLE_HELP = 'Select the column identifying each product, such as ABC-123 or 21334. This is an identifier, not a product description.'
PRICE_HELP = 'Select a monetary value column. Use the same currency and accounting convention in both lists.'

CATALOG = SetupStep('catalog', 'Product identifiers', 'general/catalog', (
    field('columns.article', 'Article / SKU column', ARTICLE_HELP),
    field('columns.family', 'Family output column', 'Name of the family column generated in reports. An existing family column may also be used.'),
    field('default_family', 'Unmatched family', 'Label for products without a matching family rule.', 'text'),
), True)
FAMILIES = SetupStep('families', 'Family rules', 'general/families', (
    field('rules', 'Families and article prefixes', 'Add a family and its prefixes. The longest matching prefix wins; equal prefixes in different families should be reviewed.', 'rules'),
), True)
NETWORK = SetupStep('network', 'Stores and locations', 'general/network', (
    field('active', 'Active stores', 'One store per line. For Stock, these must match the stock quantity headers.', 'list'),
    field('stock_database_columns', 'Store to deposit columns', 'Map a store to its deposit quantity column. Leave empty if no deposit column is used.', 'mapping'),
    field('regional_groups', 'Regional groups', 'Optional named groups of stores. Separate members with commas.', 'groups'),
), True)

STEPS = {
    'cross_check': (CATALOG, FAMILIES,
        SetupStep('cross_input', 'System stock quantities', 'cross_check/settings', (
            field('input.quantity_column', 'System quantity column', 'Column containing the recorded quantity for each article.'),)),
        SetupStep('cross_cost', 'Cost price list', 'cross_check/settings', (
            field('price_lists.cost.article_column', 'Cost-list article column', ARTICLE_HELP),
            field('price_lists.cost.price_column', 'Cost-list price column', PRICE_HELP))),
        SetupStep('cross_sales', 'Sales price list', 'cross_check/settings', (
            field('price_lists.sales.article_column', 'Sales-list article column', ARTICLE_HELP),
            field('price_lists.sales.price_column', 'Sales-list price column', PRICE_HELP))),
        SetupStep('cross_policy', 'Matching and reconciliation', 'cross_check/settings', (
            field('pricing.article_tokenization', 'Price-list article matching', 'first_token uses text before the first space; whole keeps the entire cleaned identifier.', 'token'),
            field('reconciliation.ignore_negative_system_stock_when_counted', 'Ignore negative system stock when counted', 'Use the counted quantity instead of subtracting negative system stock.', 'bool'))),
        SetupStep('cross_filters', 'Excluded articles', 'cross_check/settings', (
            field('filters.ignored_articles', 'Ignored articles', 'One exact article identifier per line; leave empty to keep all articles.', 'list'),
            field('filters.ignored_terms', 'Ignored terms', 'One filtering term per line. Review these terms before excluding articles.', 'list')))),
    'stock_processing': (CATALOG, FAMILIES, NETWORK,
        SetupStep('stock_cleaning', 'Stock cleaning', 'stock_processing/settings', (
            field('cleaning.text_columns', 'Trim text columns', 'One column name per line.', 'list'),
            field('cleaning.numeric_columns', 'Numeric columns', 'One quantity/value column name per line.', 'list'),
            field('cleaning.drop_columns', 'Remove columns', 'Columns to exclude. Do not remove required identifiers or quantities.', 'list'))),
        SetupStep('stock_prices', 'Price-list columns', 'stock_processing/settings', (
            field('pricing.columns.article', 'Price-list article column', ARTICLE_HELP),
            field('pricing.columns.database', 'Price-list store / origin column', 'Column identifying the store or origin for a price.'),
            field('pricing.columns.price', 'Price column', PRICE_HELP))),
        SetupStep('stock_matching', 'Price matching', 'stock_processing/settings', (
            field('pricing.article_tokenization', 'Article matching', 'first_token uses text before a space; whole preserves the full identifier.', 'token'),
            field('pricing.aliases', 'Origin aliases', 'Map price-list origins to configured stores.', 'mapping'))),
        SetupStep('stock_output', 'Workbook layout', 'stock_processing/settings', (
            field('output.raw_data_sheet', 'Raw-data sheet name', 'Name of the sheet containing processed stock.', 'text'),
            field('output.base_columns', 'Leading output columns', 'One header per line; include the configured article and family headers.', 'list'))),
        SetupStep('stock_summaries', 'Summary sheets', 'stock_processing/settings', (
            field('output.summaries', 'Summary sheets and stores', 'Each row defines a sheet, its stores and display titles. Leave empty to omit extra summaries.', 'summaries'),))),
    'yoy_reports': (CATALOG, FAMILIES,
        SetupStep('yoy_period', 'Sales dates and quantities', 'yoy_reports/settings', (
            field('input.date_column', 'Date column', 'Column containing transaction dates, used to select current and prior-year periods.'),
            field('input.quantity_column', 'Units sold column', 'Quantity of units on each transaction line.'),
            field('input.sales_column', 'Sales amount column', 'Total revenue of each transaction line, not its unit price. Used only when revenue is enabled.'))),
        SetupStep('yoy_products', 'Products and locations', 'yoy_reports/settings', (
            field('input.item_column', 'Article / SKU column', ARTICLE_HELP),
            field('input.grouping_column', 'Family column', 'Existing family header or the name generated from prefix rules.'),
            field('input.branch_column', 'Store / location column', 'Transaction store identifiers must match the report-group members.'))),
        SetupStep('yoy_groups', 'Comparison groups', 'yoy_reports/settings', (
            field('groups', 'Report groups and stores', 'Name a group and list its stores. Multi-store groups get a Global comparison; single-store groups do not.', 'groups'),)),
        SetupStep('yoy_sizes', 'Size breakdown', 'yoy_reports/settings', (
            field('input.size_column', 'Size column', 'Header used only when the optional size breakdown is requested.'),
            field('output.include_sizes', 'Default size breakdown', 'Enable only when your sales file contains size values.', 'bool'))),
        SetupStep('yoy_output', 'Report preferences', 'yoy_reports/settings', (
            field('output.default_path', 'Default report filename', 'A filename ending in .xlsx, or a filename without an extension.', 'text'),
            field('output.annual_comparison', 'Prior-year comparisons for monthly reports', 'Interactive full reports have a separate per-run comparison option.', 'bool'),
            field('output.metrics', 'Metrics for direct engine calls', 'Interactive CLI/GUI runs always ask separately before including revenue.', 'list')))),
}
MODULE_LABELS = {'cross_check': 'Cross Check', 'stock_processing': 'Stock Processing', 'yoy_reports': 'YoY Reports'}


def get_value(data, path):
    for key in path:
        data = data[key]
    return data


def set_value(data, path, value):
    for key in path[:-1]:
        data = data.setdefault(key, {})
    data[path[-1]] = value
