"""Inspect selected workbook schemas without writing reports or profile data."""

import pandas as pd

from core import input_doctor


class Config:
    def get_catalog_columns(self):
        return {'article': 'Item'}

    def get_cross_check_config(self):
        return {'input': {'quantity_column': 'Count'}, 'price_lists': {
            name: {'article_column': 'Item', 'price_column': 'Price'} for name in ('cost', 'sales')}}

    def get_stock_pricing(self):
        return {'columns': {'article': 'Item', 'database': 'Origin', 'price': 'Price'}}

    def get_network_config(self):
        return {'active': ['Store A'], 'stock_database_columns': {'Store A': 'Deposit A'}}

    def get_yoy_reports_config(self):
        return {'input': {'date_column': 'Date', 'quantity_column': 'Units',
            'branch_column': 'Branch', 'grouping_column': 'Family', 'item_column': 'Item',
            'sales_column': 'Revenue', 'size_column': 'Size'}}


def workbook(tmp_path, name, data, *, header=True):
    path = tmp_path / name
    pd.DataFrame(data).to_excel(path, index=False, header=header)
    return str(path)


def test_cross_check_inspects_scanner_as_headerless_and_reports_missing_prices(tmp_path, monkeypatch):
    monkeypatch.setattr(input_doctor, 'ConfigurationManager', lambda _profile: Config())
    system = workbook(tmp_path, 'system.xlsx', {'Item': ['A'], 'Count': [1]})
    scanner = workbook(tmp_path, 'scanner.xlsx', [['A'], ['B']], header=False)
    cost = workbook(tmp_path, 'cost.xlsx', {'Item': ['A'], 'Price': [10]})
    sales = workbook(tmp_path, 'sales.xlsx', {'Item': ['A'], 'Price': [12]})
    files = {'system': system, 'count': scanner, 'cost': cost, 'sales': sales}
    assert input_doctor.inspect_workflow_inputs('example', 'cross_check', files).ready
    files['sales'] = workbook(tmp_path, 'incomplete.xlsx', {'Item': ['A'], 'Amount': [12]})
    report = input_doctor.inspect_workflow_inputs('example', 'cross_check', files)
    assert not report.ready
    assert report.files[1].headerless
    assert 'Missing Sales price' in report.render()


def test_yoy_only_checks_columns_used_by_selected_options(tmp_path, monkeypatch):
    monkeypatch.setattr(input_doctor, 'ConfigurationManager', lambda _profile: Config())
    path = workbook(tmp_path, 'sales.xlsx', {'Date': ['2026-01-01'], 'Units': [2],
        'Branch': ['A'], 'Item': ['SKU']})
    files = {'file': path}
    assert input_doctor.inspect_workflow_inputs('example', 'yoy_reports', files,
        grouping='item', has_families=False).ready
    selected = input_doctor.inspect_workflow_inputs('example', 'yoy_reports', files,
        grouping='item', has_families=False, include_sales=True, include_sizes=True)
    assert not selected.ready
    assert 'Revenue' in selected.render() and 'Size' in selected.render()


def test_stock_detects_missing_configured_store_and_deposit(tmp_path, monkeypatch):
    monkeypatch.setattr(input_doctor, 'ConfigurationManager', lambda _profile: Config())
    stock = workbook(tmp_path, 'stock.xlsx', {'Item': ['A']})
    prices = workbook(tmp_path, 'prices.xlsx', {'Item': ['A'], 'Origin': ['A'], 'Price': [1]})
    report = input_doctor.inspect_workflow_inputs('example', 'stock_processing',
        {'stock': stock, 'cost': prices, 'sales': prices})
    assert not report.ready
    assert 'Store A' in report.render() and 'Deposit A' in report.render()
