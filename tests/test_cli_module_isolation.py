"""A broken enabled workflow must not prevent another workflow from running."""
import pandas as pd
import pytest

from core import paths
from core.json_documents import read_document, write_documents
from core.profile_creation import create_profile
from cli import stock_processing_launcher, cross_check_launcher


@pytest.mark.parametrize('module', ['stock_processing', 'cross_check'])
def test_cli_runs_with_unrelated_invalid_enabled_settings(tmp_path, monkeypatch, module):
    monkeypatch.setattr(paths, 'PROFILES_ROOT', tmp_path / 'profiles')
    profile = create_profile('Independent run', '', ['stock_processing', 'cross_check', 'yoy_reports'])
    root = paths.profile_configs_root(profile)
    (root / 'yoy_reports/settings.json').write_text('broken JSON')
    network = read_document(root / 'general/network.json'); network['active'] = ['Counter']
    stock = read_document(root / 'stock_processing/settings.json'); stock['pricing']['default_store'] = 'Counter'
    write_documents({root / 'general/network.json': network, root / 'stock_processing/settings.json': stock})
    prices = tmp_path / 'prices.xlsx'
    pd.DataFrame({'SKU': ['A'], 'Cost': [2], 'Price': [5]}).to_excel(prices, index=False)
    source = tmp_path / 'input.xlsx'; output = tmp_path / 'output.xlsx'
    if module == 'stock_processing':
        pd.DataFrame({'SKU': ['A'], 'Counter': [2]}).to_excel(source, index=False)
        selected = [source, prices, prices, output]
        launcher, run = stock_processing_launcher, stock_processing_launcher.launch_stock_processing
    else:
        pd.DataFrame({'SKU': ['A'], 'Quantity': [1]}).to_excel(source, index=False)
        count = tmp_path / 'count.xlsx'
        pd.DataFrame(['A', 'A']).to_excel(count, index=False, header=False)
        selected = [source, count, prices, prices, output]
        launcher, run = cross_check_launcher, cross_check_launcher.launch_cross_check
    choices = iter(map(str, selected))
    monkeypatch.setattr(launcher, 'ask_file', lambda *_args, **_kwargs: next(choices))
    monkeypatch.setattr(launcher, 'clear_screen', lambda: None)
    monkeypatch.setattr('builtins.input', lambda *_args: '')
    run(profile)
    assert output.is_file()
    assert (root / 'yoy_reports/settings.json').read_text() == 'broken JSON'
