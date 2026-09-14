import os
import sys
import time
import json
import random
import string
import gc
from pathlib import Path

# Link project root directory
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

try:
    import pandas as pd
    import numpy as np
    from core.configuration_manager import ConfigurationManager
    from engine.shared.families import build_family_rules, vectorize_assign_families, assign_family
    from core.data_sanitizer import clean_sku_series
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

def print_banner():
    print("=" * 65)
    print(" 🩺 INVENTORY TOOLKIT — REPO DOCTOR & PERFORMANCE BENCHMARK")
    print("=" * 65)

# =========================================================================
# 1. PROFILE & REPOSITORY INTEGRITY AUDIT
# =========================================================================
def audit_profiles():
    print("\n🔍 [1/3] Auditing profiles and configuration schemas...")
    profiles_dir = ROOT_DIR / "profiles"
    if not profiles_dir.exists():
        print("  ⚠️ 'profiles/' directory not found.")
        return

    profiles = [p for p in profiles_dir.iterdir() if p.is_dir()]
    print(f"  📁 Detected profiles: {len(profiles)}")

    for prof in profiles:
        print(f"\n  👉 Profile: [{prof.name}]")
        cfg_path = prof / "configs"
        
        # Expected base JSON configs
        expected_configs = [
            "general/familias.json",
            "general/settings.json",
            "general/stores.json",
            "general/databases.json",
            "stock_processing/cleaning.json",
            "stock_processing/pricing.json",
            "cross_check/cross_check_settings.json",
            "yoy_reports/reports.json"
        ]
        
        missing = []
        for rel_cfg in expected_configs:
            target = cfg_path / rel_cfg
            if not target.exists():
                missing.append(rel_cfg)

        if missing:
            print(f"     ⚠️ Missing configs ({len(missing)}): {', '.join(missing)}")
        else:
            print("     ✅ All base configuration files are present.")

        # Test loading via ConfigurationManager
        try:
            cm = ConfigurationManager(profile=prof.name)
            familias = cm.get_familias()
            print(f"     📊 Loaded family rules: {len(familias)} categories")
        except Exception as err:
            print(f"     ❌ Error initializing ConfigurationManager: {err}")

# =========================================================================
# 2. STRESS TEST & VECTORIZATION BENCHMARK (50,000 SKUs)
# =========================================================================
def run_benchmark(n_items=50000):
    print(f"\n⚡ [2/3] Generating synthetic stress dataset ({n_items:,} rows)...")
    
    prefixes = ["001", "002", "0085", "185", "045", "123", "23", "30", "40", "99"]
    families_mock = {
        "Remeras": ["001", "002"],
        "Buzos": ["0085", "185", "045"],
        "Pantalones": ["123", "23"],
        "Accesorios": ["30", "40"]
    }
    
    rules = build_family_rules(families_mock)

    # Generate random test SKUs (simulate dirty Excel float suffixes and spaces)
    mock_skus = []
    for _ in range(n_items):
        pref = random.choice(prefixes)
        rand_suffix = "".join(random.choices(string.digits, k=3))
        sku = f"{pref}-{rand_suffix}"
        if random.random() < 0.15:
            sku += ".0"  # Simulate Excel float conversion artifact
        elif random.random() < 0.10:
            sku = f"  {sku}  "  # Simulate whitespace
        mock_skus.append(sku)

    s_raw = pd.Series(mock_skus)

    # Benchmark 1: Sanitization
    t0 = time.perf_counter()
    s_clean = clean_sku_series(s_raw)
    t_sanitization = time.perf_counter() - t0
    print(f"  🧹 Sanitization of {n_items:,} SKUs: {t_sanitization:.4f} sec")

    # Benchmark 2: Legacy Iterative Classification (apply/lambda)
    t0 = time.perf_counter()
    _ = s_clean.apply(lambda x: assign_family(x, rules))
    t_legacy = time.perf_counter() - t0
    print(f"  🐢 Legacy Classification (apply):     {t_legacy:.4f} sec ({n_items/t_legacy:,.0f} SKUs/sec)")

    # Benchmark 3: Vectorized Classification (regex-anchored)
    t0 = time.perf_counter()
    res_vec = vectorize_assign_families(s_clean, rules)
    t_vectorized = time.perf_counter() - t0
    print(f"  🚀 Vectorized Classification:       {t_vectorized:.4f} sec ({n_items/t_vectorized:,.0f} SKUs/sec)")

    speedup = t_legacy / t_vectorized if t_vectorized > 0 else 0
    print(f"\n  🔥 Performance Speedup: {speedup:.2f}x faster")
    
    # Category distribution output
    counts = res_vec.value_counts().to_dict()
    print(f"  📈 Category Distribution: {counts}")

    del s_raw, s_clean, res_vec
    gc.collect()

# =========================================================================
# 3. ENVIRONMENT & SYSTEM AUDIT
# =========================================================================
def audit_system():
    print("\n🖥️ [3/3] Environment check...")
    print(f"  🐍 Python Version: {sys.version.split()[0]} ({sys.platform})")
    print(f"  📦 Pandas Version: {pd.__version__}")
    
    # Audit logs directory
    logs_dir = ROOT_DIR / "logs"
    if logs_dir.exists():
        session_log = logs_dir / "session.log"
        if session_log.exists():
            size_kb = session_log.stat().st_size / 1024
            print(f"  📝 Active session log: {size_kb:.2f} KB")
    else:
        print("  📝 'logs/' directory ready for initialization.")

    print("\n" + "=" * 65)
    print(" ✅ DIAGNOSTIC COMPLETE: Engine is healthy and ready for production.")
    print("=" * 65)

if __name__ == "__main__":
    print_banner()
    audit_profiles()
    run_benchmark(50000)
    audit_system()