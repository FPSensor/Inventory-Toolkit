"""Presentation-neutral guided setup steps; labels never expose storage keys."""
from dataclasses import dataclass


@dataclass(frozen=True)
class SetupField:
    path: tuple[str, ...]
    label: str
    help: str
    kind: str = 'column'
    hint_key: str | None = None
    sample_required: bool = True
    optional: bool = False
    choices: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class SetupStep:
    id: str
    title: str
    logical: str
    fields: tuple[SetupField, ...]
    shared: bool = False
    advanced: bool = False
    condition: tuple[str, str] | None = None
    sample: str | None = None


def field(path, label, help, kind='column', *, hint_key=None, sample_required=True, optional=False, choices=()):
    return SetupField(tuple(path.split('.')), label, help, kind, hint_key, sample_required, optional, tuple(choices))


ARTICLE_HELP = 'Select the column identifying each product, such as ABC-123 or 21334. This is an identifier, not a product description.'
PRICE_HELP = 'Select a monetary value column. Use the same currency and accounting convention in both lists.'

CATALOG = SetupStep('catalog', 'Report labels', 'general/catalog', (
    field('columns.article', 'Product-code output heading', 'Heading used for product identifiers in generated Stock and Cross Check reports. Input-file headers are mapped separately.', 'text'),
    field('columns.family', 'Category output heading', 'Heading for categories generated in reports.', 'text'),
    field('default_family', 'Unmatched family', 'Label for products without a matching family rule.', 'text'),
), True)
FAMILIES = SetupStep('families', 'Family rules', 'general/families', (
    field('rules', 'Families and article prefixes', 'Add a family and its prefixes. The longest matching prefix wins; equal prefixes in different families should be reviewed.', 'rules'),
), True)
NETWORK = SetupStep('network', 'Your locations', 'general/network', (
    field('active', 'Locations to include', 'Add stable names for your shops, warehouses or counters. Spreadsheet column names are configured separately.', 'list'),
), True)
NETWORK_GROUPS = SetupStep('network_groups', 'Location groups', 'general/network', (
    field('regional_groups', 'Groups of locations', 'Optional groups used by Stock summaries. Each member must be a configured Stock location.', 'groups'),
), True, advanced=True)

MATCHING = (("Keep the full product code", "whole"), ("Use only the first word", "first_token"))


def classification_step(module):
    return SetupStep('classification', 'Where do your categories come from?', f'{module}/settings', (
        field('input.family_mode', 'Product categories', 'Use an existing category column, classify codes by prefix, or keep one default category.', 'choice', choices=(("Use a category column in this file", "column"), ("Classify product codes by prefix", "rules"), ("Do not classify products", "none"))),
        field('input.family_column', 'Category column (when used)', 'The exact category header in this module’s stock file. It does not change the sales-history mapping.', hint_key='family_hints', optional=True),
    ), sample='stock' if module == 'stock_processing' else 'system')


def price_step(side):
    return SetupStep(f'stock_{side}', f'{side.title()} price columns', 'stock_processing/settings', (
        field(f'pricing.{side}_columns.article', 'Product code', ARTICLE_HELP, hint_key='article_hints'),
        field(f'pricing.{side}_columns.price', 'Unit price', PRICE_HELP, hint_key='price_hints'),
        field(f'pricing.{side}_columns.database', 'Location column (optional)', 'Leave blank if the whole price list applies to one location. Choose that location on the next page.', hint_key='db_hints', optional=True),
    ), sample=side)


STEPS = {
    'cross_check': (CATALOG, classification_step('cross_check'), FAMILIES,
        SetupStep('cross_input', 'System stock columns', 'cross_check/settings', (
            field('input.article_column', 'Product code', ARTICLE_HELP, hint_key='article_hints'),
            field('input.quantity_column', 'Recorded quantity', 'Quantity currently recorded for each product.', hint_key='qty_hints')), sample='system'),
        SetupStep('cross_count_mode', 'How was the physical count recorded?', 'cross_check/settings', (
            field('input.count_mode', 'Count format', 'Scanner: one headerless line per unit. Quantity table: a product code and its counted quantity on each row.', 'choice', choices=(("One scanner reading per unit", "scans"), ("Table with counted quantities", "quantities"))),
            field('input.matching', 'Product matching', 'Exact matching never guesses a product from a longer code. Prefix matching supports scanner suffixes.', 'choice', choices=(("Exact product codes", "exact"), ("Longest known prefix", "longest_prefix"))))),
        SetupStep('cross_count_columns', 'Physical count columns', 'cross_check/settings', (
            field('input.count_article_column', 'Counted product code', ARTICLE_HELP, hint_key='article_hints'),
            field('input.count_quantity_column', 'Counted quantity', 'A nonnegative measured count, including fractions when appropriate.', hint_key='qty_hints')),
            condition=('input.count_mode', 'quantities'), sample='count'),
        SetupStep('cross_cost', 'Cost price columns', 'cross_check/settings', (
            field('price_lists.cost.article_column', 'Product code', ARTICLE_HELP, hint_key='article_hints'),
            field('price_lists.cost.price_column', 'Unit cost', PRICE_HELP, hint_key='price_hints')), sample='cost'),
        SetupStep('cross_sales', 'Sales price columns', 'cross_check/settings', (
            field('price_lists.sales.article_column', 'Product code', ARTICLE_HELP, hint_key='article_hints'),
            field('price_lists.sales.price_column', 'Unit sales price', PRICE_HELP, hint_key='price_hints')), sample='sales'),
        SetupStep('cross_policy', 'Reconciliation preferences', 'cross_check/settings', (
            field('reconciliation.ignore_negative_system_stock_when_counted', 'Ignore negative system stock when counted', 'Use the counted quantity instead of subtracting negative system stock.', 'bool'),
            field('reconciliation.quantity_tolerance', 'Ignore differences smaller than this amount', 'Zero keeps every nonzero difference. A small positive tolerance can ignore fractional measurement noise.', 'number'),
            field('pricing.article_tokenization', 'Price-list product codes', 'Keep the full identifier unless the file adds descriptions after a space.', 'choice', choices=MATCHING)), advanced=True),
        SetupStep('cross_filters', 'Products to exclude', 'cross_check/settings', (
            field('filters.ignored_articles', 'Exact product codes to ignore', 'Leave empty to keep every product.', 'list'),
            field('filters.ignored_terms', 'Text to exclude', 'Any product code containing these terms is excluded. Use this only for known export totals or placeholders.', 'list')), advanced=True)),
    'stock_processing': (CATALOG, classification_step('stock_processing'), FAMILIES, NETWORK,
        SetupStep('stock_layout', 'How is stock arranged?', 'stock_processing/settings', (
            field('input.format', 'Stock layout', 'Wide: one quantity column per location. Row-based: one quantity and an optional location per row.', 'choice', choices=(("One quantity column per location", "wide"), ("One product/location per row", "long"))),
            field('input.article_column', 'Stock product code', ARTICLE_HELP, hint_key='article_hints')), sample='stock'),
        SetupStep('stock_input', 'Quantity columns by location', 'stock_processing/settings', (
            field('input.quantity_columns', 'Location and its quantity header', 'Left: the location name. Right: its exact quantity header in your stock file.', 'mapping'),
            field('input.deposit_columns', 'Additional deposit quantity headers', 'Optional additional quantities to add to each location. Leave empty if not used.', 'mapping')),
            condition=('input.format', 'wide'), sample='stock'),
        SetupStep('stock_long', 'Row-based stock quantities', 'stock_processing/settings', (
            field('input.quantity_column', 'Quantity column', 'Numeric stock quantity, including fractional values.', hint_key='qty_hints'),
            field('input.branch_column', 'Location column (optional)', 'Leave blank if every row belongs to one location.', hint_key='branch_hints', optional=True),
            field('input.default_store', 'Single location when no column is used', 'Use one of the location names you added earlier.', 'text', optional=True)), condition=('input.format', 'long'), sample='stock'),
        price_step('cost'), price_step('sales'),
        SetupStep('stock_price_location', 'Prices without a location column', 'stock_processing/settings', (
            field('pricing.default_store', 'Location for simple price lists', 'Needed only when a price list has no location column. Leave empty when both lists map their own location column.', 'text', optional=True),)),
        SetupStep('stock_cleaning', 'Optional export cleanup', 'stock_processing/settings', (
            field('cleaning.text_columns', 'Text columns to trim', 'Product identifiers are always cleaned. Add other text headers only when useful.', 'list'),
            field('cleaning.numeric_columns', 'Other numeric columns', 'Location quantities are always numeric. Add extra numeric headers if needed.', 'list'),
            field('cleaning.drop_columns', 'Columns to remove', 'Optional export clutter. Required product and quantity columns must be kept.', 'list')), advanced=True),
        SetupStep('stock_matching', 'Price matching', 'stock_processing/settings', (
            field('pricing.article_tokenization', 'Product codes in price lists', 'Keep the full identifier unless the file appends descriptions after a space.', 'choice', choices=MATCHING),
            field('pricing.aliases', 'Price-origin names and matching locations', 'Map each source origin value to your stable location name.', 'mapping')), advanced=True),
        SetupStep('stock_output', 'Workbook detail layout', 'stock_processing/settings', (
            field('output.raw_data_sheet', 'Detail sheet name', 'Name of the processed stock sheet.', 'text'),
            field('output.base_columns', 'Product details to retain', 'One header per line, in output order. Include product/family output names and any variant or description columns you want.', 'list')), advanced=True),
        SetupStep('stock_quantities', 'Quantity display', 'stock_processing/settings', (
            field('output.quantity_label', 'Quantity unit', 'For example units, kg or liters. Inventory Toolkit does not convert units.', 'text'),
            field('output.quantity_format', 'Excel quantity format', 'Whole units: #,##0. Fractions: #,##0.###.', 'text'))),
        SetupStep('stock_summaries', 'Optional summary sheets', 'stock_processing/settings', (
            field('output.summaries', 'Summary sheets', 'Choose a sheet name and its locations. Display titles may be left empty.', 'summaries'),), advanced=True), NETWORK_GROUPS),
    'yoy_reports': (CATALOG, FAMILIES,
        SetupStep('yoy_period', 'Sales dates and amounts', 'yoy_reports/settings', (
            field('input.date_column', 'Transaction date', 'Dates used to select current and previous-year periods.', hint_key='date_hints'),
            field('input.quantity_column', 'Quantity sold', 'Quantity on each sale line; fractions are supported.', hint_key='qty_hints'),
            field('input.sales_column', 'Line revenue (optional)', 'Total amount of a sale line, not the unit price. Only needed when revenue comparison is enabled.', hint_key='sales_hints', optional=True)), sample='file'),
        SetupStep('yoy_products', 'Products and locations in sales', 'yoy_reports/settings', (
            field('input.item_column', 'Sales product code', ARTICLE_HELP, hint_key='article_hints'),
            field('input.grouping_column', 'Family/category column', 'Existing category header, or the category name to generate from prefix rules.', hint_key='family_hints', sample_required=False),
            field('input.branch_column', 'Sales location column', 'Values must match the members of your comparison groups.', hint_key='branch_hints')), sample='file'),
        SetupStep('yoy_groups', 'Which locations should be compared?', 'yoy_reports/settings', (
            field('groups', 'Comparison groups and their locations', 'One group can contain one or more locations. A multi-location group gets a Global block; one-location groups do not duplicate totals.', 'groups'),)),
        SetupStep('yoy_variants', 'Optional product variants', 'yoy_reports/settings', (
            field('output.include_variants', 'Include variants by default', 'Leave off when products do not use variants.', 'bool'),
            field('input.variant_column', 'Variant column (optional)', 'For example package weight, flavor or size. This identifies a product dimension; it is separate from quantity sold.', hint_key='variant_hints', sample_required=False, optional=True)), sample='file'),
        SetupStep('yoy_quantities', 'Quantity display', 'yoy_reports/settings', (
            field('output.quantity_label', 'Quantity metric name', 'For example Units Sold or Quantity (kg).', 'text'),
            field('output.quantity_format', 'Excel quantity format', 'Whole units: #,##0. Fractions: #,##0.###.', 'text'))),
        SetupStep('yoy_output', 'Additional report preferences', 'yoy_reports/settings', (
            field('output.default_path', 'Suggested report filename', 'A .xlsx filename. An omitted extension is added automatically.', 'text'),
            field('output.annual_comparison', 'Compare prior year in monthly reports', 'Full reports ask separately for the comparison option.', 'bool'),
            field('output.metrics', 'Metrics for direct engine calls', 'Interactive runs ask separately before including revenue.', 'metrics')), advanced=True)),
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
