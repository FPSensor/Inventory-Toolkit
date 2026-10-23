"""Resolve module-specific input contracts without frontend decisions."""


def stock_input(config):
    settings = config.get_stock_processing_config()
    source = dict(settings["input"])
    source["article_column"] = source["article_column"] or config.get_catalog_columns()["article"]
    network = config.get_network_config()
    source["quantity_columns"] = source["quantity_columns"] or {store: store for store in network["active"]}
    if source["deposit_columns"] is None:
        source["deposit_columns"] = network["stock_database_columns"]
    return source


def stock_price_columns(config, side, *, required_only=False):
    pricing = config.get_stock_pricing()
    columns = pricing.get(f"{side}_columns") or pricing["columns"]
    return {key: value for key, value in columns.items() if value} if required_only else columns


def cross_article_column(config):
    return config.get_cross_check_config()["input"]["article_column"] or config.get_catalog_columns()["article"]
