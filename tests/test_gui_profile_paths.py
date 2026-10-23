"""Profile switches must not retain another profile's workbook selections."""
from types import SimpleNamespace
from gui import app


class Variable:
    def __init__(self, value=''):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


def test_inventory_paths_restore_and_clear_independently(monkeypatch):
    saved = {'stock_processing': {'stock': 'stock.xlsx', 'out': 'valuations.xlsx'},
             'cross_check': {'system': 'system.xlsx', 'count': 'count.xlsx'}}
    monkeypatch.setattr(app, 'load_last_paths', lambda _profile: saved)
    view = SimpleNamespace(active_profile=Variable('first'), **{name: Variable('previous.xlsx')
        for name in ('sp_raw','sp_cost','sp_sales','sp_out','cc_sys','cc_count','cc_cost','cc_sales','cc_out')})
    app.InventoryToolkitGUI._restore_inventory_paths(view)
    assert view.sp_raw.get() == 'stock.xlsx' and view.sp_out.get() == 'valuations.xlsx'
    assert view.cc_sys.get() == 'system.xlsx' and view.cc_count.get() == 'count.xlsx'
    assert view.sp_cost.get() == '' and view.cc_sales.get() == ''
    saved.clear()
    view.active_profile.set('second')
    app.InventoryToolkitGUI._restore_inventory_paths(view)
    assert view.sp_raw.get() == '' and view.cc_sys.get() == ''
