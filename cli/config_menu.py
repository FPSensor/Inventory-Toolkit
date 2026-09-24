"""Configuration Hub for the current Inventory Toolkit configuration schema.

The hub is organized by business module, not by JSON filename.  JSON remains
human-readable storage, but users no longer need to know where a setting lives.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from cli.utils import ask_yes_no, clear_screen, load_json, save_json
from cli.wizard import run_setup_wizard
from core.configuration_manager import ConfigurationManager
from core.profile_config import config_path, ensure_profile_config, migrate_legacy_config, profile_readiness

PROFILES_DIR = "profiles"


def _pause(msg="Press Enter..."):
    input(f"  {msg}")


def _header(title, profile):
    print("=" * 72); print(f"  ⚙️  {title} — [{profile}]"); print("=" * 72)


def _edit_scalar(data: dict, key: str, label: str):
    current = data.get(key, "")
    raw = input(f"  {label} [Enter={current}]: ").strip()
    if raw:
        if isinstance(current, bool): data[key] = raw.lower() in ("true", "yes", "y", "1")
        else: data[key] = raw


def _edit_list(data: dict, key: str, label: str):
    current = data.get(key, [])
    raw = input(f"  {label} comma-separated [Enter keeps {len(current)}]: ").strip()
    if raw:
        data[key] = [x.strip() for x in raw.split(",") if x.strip()]


def _family_editor(path: Path, profile: str):
    while True:
        data = load_json(str(path)) or {"version": 3, "rules": {}}
        rules = data.setdefault("rules", {})
        clear_screen(); _header("Catalog → Family rules", profile)
        query = input("  Search family (Enter shows all, 0 back): ").strip()
        if query == "0": return
        names = [n for n in sorted(rules) if query.lower() in n.lower()]
        for i, name in enumerate(names, 1):
            print(f"  [{i:02d}] {name:<34} {', '.join(rules[name])}")
        print("\n  [A] Add family  [E] Edit family  [D] Delete family  [0] Back")
        cmd = input("  Action: ").strip().upper()
        if cmd == "0": return
        if cmd == "A":
            name = input("  Family name: ").strip()
            prefixes = input("  Prefixes comma-separated: ").strip()
            if name: rules[name] = [x.strip() for x in prefixes.split(",") if x.strip()]
        elif cmd in ("E", "D"):
            raw = input("  Family number: ").strip()
            if raw.isdigit() and 1 <= int(raw) <= len(names):
                name = names[int(raw)-1]
                if cmd == "D" and ask_yes_no(f"Delete '{name}'?"): rules.pop(name, None)
                elif cmd == "E":
                    new_name = input(f"  Name [Enter={name}]: ").strip() or name
                    prefixes = input(f"  Prefixes [Enter={', '.join(rules[name])}]: ").strip()
                    value = rules[name] if not prefixes else [x.strip() for x in prefixes.split(",") if x.strip()]
                    if new_name != name: rules.pop(name)
                    rules[new_name] = value
        data["rules"] = rules; save_json(str(path), data)


def _catalog_menu(configs: Path, profile: str):
    while True:
        catalog_path = config_path(configs, "general/catalog")
        catalog = load_json(str(catalog_path)) or {}
        cols = catalog.setdefault("columns", {})
        clear_screen(); _header("Catalog & Families", profile)
        print(f"  Article column : {cols.get('article','Artículo')}")
        print(f"  Family column  : {cols.get('family','Familias')}")
        print(f"  Default family : {catalog.get('default_family','Otro')}")
        fam = load_json(str(config_path(configs, 'general/families'))) or {}
        print(f"  Family rules   : {len(fam.get('rules',{}))}")
        print("\n  [1] Core columns/default  [2] Family rules  [0] Back")
        cmd = input("  Option: ").strip()
        if cmd == "0": return
        if cmd == "1":
            _edit_scalar(cols, "article", "Article column")
            _edit_scalar(cols, "family", "Family column")
            _edit_scalar(catalog, "default_family", "Default family")
            catalog["columns"] = cols; save_json(str(catalog_path), catalog)
        elif cmd == "2": _family_editor(config_path(configs, "general/families"), profile)


def _network_menu(configs: Path, profile: str):
    path = config_path(configs, "general/network")
    while True:
        data = load_json(str(path)) or {"version": 3, "active": [], "regional_groups": {}, "stock_database_columns": {}}
        clear_screen(); _header("Stores & Network", profile)
        print(f"  Active stores: {', '.join(data.get('active',[])) or '—'}")
        print("  Regional groups:")
        for k,v in data.get("regional_groups",{}).items(): print(f"    {k} → {', '.join(v)}")
        print("  Stock database columns:")
        for k,v in data.get("stock_database_columns",{}).items(): print(f"    {k} → {v}")
        print("\n  [1] Active stores  [2] Regional groups  [3] Database-column map  [0] Back")
        cmd=input("  Option: ").strip()
        if cmd=="0": return
        if cmd=="1": _edit_list(data,"active","Active stores")
        elif cmd=="2":
            name=input("  Group name (prefix '-' to delete): ").strip()
            if name.startswith("-"): data.setdefault("regional_groups",{}).pop(name[1:],None)
            elif name:
                raw=input("  Members comma-separated: ").strip(); data.setdefault("regional_groups",{})[name]=[x.strip() for x in raw.split(",") if x.strip()]
        elif cmd=="3":
            store=input("  Store (prefix '-' to delete): ").strip()
            if store.startswith("-"): data.setdefault("stock_database_columns",{}).pop(store[1:],None)
            elif store:
                col=input("  Raw database/deposit column: ").strip()
                if col: data.setdefault("stock_database_columns",{})[store]=col
        save_json(str(path),data)


def _stock_menu(configs: Path, profile: str):
    path=config_path(configs,"stock_processing/settings")
    while True:
        d=load_json(str(path)) or {}; clean=d.setdefault("cleaning",{}); price=d.setdefault("pricing",{}); out=d.setdefault("output",{})
        clear_screen(); _header("Stock Processing",profile)
        print(f"  Cleaning: {len(clean.get('drop_columns',[]))} drops / {len(clean.get('text_columns',[]))} text / {len(clean.get('numeric_columns',[]))} numeric")
        print(f"  Pricing columns: {price.get('columns',{})}")
        print(f"  Output: sheet={out.get('raw_data_sheet','Datos')} | {len(out.get('summaries',[]))} summaries")
        print("\n  [1] Cleaning  [2] Pricing  [3] Output layout  [4] Summary sheets  [0] Back")
        cmd=input("  Option: ").strip()
        if cmd=="0": return
        if cmd=="1":
            _edit_list(clean,"text_columns","Text columns"); _edit_list(clean,"numeric_columns","Numeric columns"); _edit_list(clean,"drop_columns","Columns to drop")
        elif cmd=="2":
            cols=price.setdefault("columns",{})
            for k,l in (("article","Article column"),("database","Database/origin column"),("price","Price column")): _edit_scalar(cols,k,l)
            print(f"  Aliases: {price.get('aliases',{})}"); raw=input("  Add alias as ORIGINAL=ALIAS (Enter skip): ").strip()
            if "=" in raw: a,b=raw.split("=",1); price.setdefault("aliases",{})[a.strip()]=b.strip()
        elif cmd=="3":
            _edit_scalar(out,"raw_data_sheet","Raw data sheet"); _edit_list(out,"base_columns","Base columns")
        elif cmd=="4":
            sums=out.setdefault("summaries",[])
            for i,s in enumerate(sums,1): print(f"  [{i}] {s.get('sheet_name')} ← {s.get('entities',[])}")
            raw=input("  [A]dd, [D]elete or Enter: ").strip().upper()
            if raw=="A":
                name=input("  Sheet name: ").strip(); stores=input("  Stores/groups comma-separated: ").strip()
                if name: sums.append({"sheet_name": name, "entities": [x.strip() for x in stores.split(",") if x.strip()], "titles": []})
            elif raw=="D":
                n=input("  Number: ").strip()
                if n.isdigit() and 1<=int(n)<=len(sums): sums.pop(int(n)-1)
        save_json(str(path),d)


def _cross_menu(configs: Path, profile: str):
    path=config_path(configs,"cross_check/settings")
    while True:
        d=load_json(str(path)) or {}; filt=d.setdefault("filters",{}); lists=d.setdefault("price_lists",{})
        clear_screen(); _header("Cross Check",profile)
        print(f"  Ignored articles: {len(filt.get('ignored_articles',[]))}")
        print(f"  Ignored terms: {', '.join(filt.get('ignored_terms',[]))}")
        print(f"  Cost columns: {lists.get('cost',{})}"); print(f"  Sales columns: {lists.get('sales',{})}")
        print("\n  [1] Filters  [2] Cost list columns  [3] Sales list columns  [0] Back")
        cmd=input("  Option: ").strip()
        if cmd=="0": return
        if cmd=="1": _edit_list(filt,"ignored_articles","Ignored articles"); _edit_list(filt,"ignored_terms","Ignored text terms")
        elif cmd in ("2","3"):
            side="cost" if cmd=="2" else "sales"; m=lists.setdefault(side,{})
            _edit_scalar(m,"article_column","Article column"); _edit_scalar(m,"price_column","Price column")
        save_json(str(path),d)


def _yoy_menu(configs: Path, profile: str):
    path=config_path(configs,"yoy_reports/settings")
    while True:
        d=load_json(str(path)) or {}; inp=d.setdefault("input",{}); out=d.setdefault("output",{}); groups=d.setdefault("groups",{})
        clear_screen(); _header("YoY Reports",profile)
        print(f"  Input mapping: {inp}"); print(f"  Output: {out}")
        print(f"  Groups: {len(groups)}")
        print("\n  [1] Input columns  [2] Output options  [3] Report groups  [0] Back")
        cmd=input("  Option: ").strip()
        if cmd=="0": return
        if cmd=="1":
            for k,l in (("date_column","Date"),("quantity_column","Quantity"),("grouping_column","Grouping/family"),("item_column","Item/SKU"),("branch_column","Branch/store"),("size_column","Size")): _edit_scalar(inp,k,l)
        elif cmd=="2":
            _edit_scalar(out,"default_path","Default output path"); _edit_list(out,"metrics","Metrics")
            for key,label in (("annual_comparison","Annual comparison"),("include_sizes","Include sizes")): _edit_scalar(out,key,label)
        elif cmd=="3":
            for k,v in groups.items(): print(f"  {k} → {', '.join(v)}")
            name=input("  Group name (prefix '-' to delete): ").strip()
            if name.startswith("-"): groups.pop(name[1:],None)
            elif name:
                raw=input("  Branches comma-separated: ").strip(); groups[name]=[x.strip() for x in raw.split(",") if x.strip()]
        save_json(str(path),d)


def _validate(profile: str):
    try:
        cm=ConfigurationManager(profile)
        cm.get_catalog(); cm.get_family_config(); cm.get_network_config(); cm.get_stock_processing_config(); cm.get_cross_check_config(); cm.get_yoy_reports_config()
        print("  ✅ All configuration files validate successfully.")
    except Exception as exc:
        print(f"  ❌ Validation failed: {exc}")
    _pause()


def configuration_menu(current_profile: str) -> None:
    configs=Path(PROFILES_DIR)/current_profile/"configs"
    migrate_legacy_config(configs, remove_legacy=False); ensure_profile_config(configs)
    while True:
        clear_screen(); _header("Configuration Hub",current_profile)
        ready=profile_readiness(configs)
        for n,(key,label) in enumerate((("catalog","Catalog & families"),("stores","Stores & network"),("stock","Stock Processing"),("cross_check","Cross Check"),("yoy","YoY Reports")),1):
            ok,detail=ready[key]; print(f"  [{n}] {'✅' if ok else '⚠️ '} {label:<22} {detail}")
        print("\n  [W] Guided Setup   [V] Validate profile   [M] Migrate/archive legacy config   [0] Back")
        cmd=input("\n  Select a module: ").strip().upper()
        if cmd=="0": return
        if cmd=="1": _catalog_menu(configs,current_profile)
        elif cmd=="2": _network_menu(configs,current_profile)
        elif cmd=="3": _stock_menu(configs,current_profile)
        elif cmd=="4": _cross_menu(configs,current_profile)
        elif cmd=="5": _yoy_menu(configs,current_profile)
        elif cmd=="W": run_setup_wizard(str(configs.parent),current_profile)
        elif cmd=="V": _validate(current_profile)
        elif cmd=="M":
            migrated = migrate_legacy_config(configs, remove_legacy=True)
            print("  ✅ Legacy configuration migrated and archived in configs/_legacy_v1_backup/." if migrated
                  else "  ℹ️  No legacy v1 files were found.")
            _pause()
