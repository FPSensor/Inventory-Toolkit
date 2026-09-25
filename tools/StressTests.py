import os
import sys
import time
import json
import random
import string
import gc
from pathlib import Path

# Link project root directory
BOOTSTRAP_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BOOTSTRAP_ROOT))

from core.paths import APPLICATION_ROOT, LOGS_ROOT, PROFILES_ROOT

ROOT_DIR = APPLICATION_ROOT

try:
    import pandas as pd
    import numpy as np
    from core.configuration_manager import ConfigurationManager
    from engine.shared.families import assign_families, assign_family, build_family_rules
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
    profiles_dir = PROFILES_ROOT
    if not profiles_dir.exists():
        print("  ⚠️ 'profiles/' directory not found.")
        return

    profiles = [p for p in profiles_dir.iterdir() if p.is_dir()]
    print(f"  📁 Detected profiles: {len(profiles)}")

    for prof in profiles:
        print(f"\n  👉 Profile: [{prof.name}]")
        cfg_path = prof / "configs"
        
        # Expected current configuration files
        expected_configs = [
            "general/catalog.json",
            "general/families.json",
            "general/network.json",
            "stock_processing/settings.json",
            "cross_check/settings.json",
            "yoy_reports/settings.json",
        ]

        missing = []
        for relative_config in expected_configs:
            target = cfg_path / relative_config
            if not target.exists():
                missing.append(relative_config)

        if missing:
            print(f"     ⚠️ Missing configs ({len(missing)}): {', '.join(missing)}")
        else:
            print("     ✅ All current configuration files are present.")

        # Test loading via ConfigurationManager
        try:
            cm = ConfigurationManager(profile=prof.name)
            families = cm.get_family_rules()
            print(f"     📊 Loaded family rules: {len(families)} categories")
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

    # Benchmark 2: Legacy full pipeline (sanitization + apply/lambda)
    t0 = time.perf_counter()
    _ = clean_sku_series(s_raw).apply(lambda x: assign_family(x, rules))
    t_legacy = time.perf_counter() - t0
    print(f"  🐢 Legacy pipeline (clean + apply): {t_legacy:.4f} sec ({n_items/t_legacy:,.0f} SKUs/sec)")

    # Benchmark 3: Batch full pipeline (sanitization + prefix trie)
    t0 = time.perf_counter()
    batch_result = assign_families(s_raw, rules)
    t_vectorized = time.perf_counter() - t0
    print(f"  🚀 Batch pipeline (clean + trie):   {t_vectorized:.4f} sec ({n_items/t_vectorized:,.0f} SKUs/sec)")

    speedup = t_legacy / t_vectorized if t_vectorized > 0 else 0
    if speedup >= 1:
        print(f"\n  🔥 Batch classifier: {speedup:.2f}x faster than apply")
    elif speedup > 0:
        slowdown = 1 / speedup
        print(f"\n  ⚠️ Batch classifier: {slowdown:.2f}x slower than apply on this dataset")
    else:
        print("\n  ⚠️ Batch benchmark could not calculate a valid ratio")
    
    # Category distribution output
    counts = batch_result.value_counts().to_dict()
    print(f"  📈 Category Distribution: {counts}")

    del s_raw, s_clean, batch_result
    gc.collect()

# =========================================================================
# 3. ENVIRONMENT & SYSTEM AUDIT
# =========================================================================
def audit_system():
    print("\n🖥️ [3/3] Environment check...")
    print(f"  🐍 Python Version: {sys.version.split()[0]} ({sys.platform})")
    print(f"  📦 Pandas Version: {pd.__version__}")
    
    # Audit logs directory
    logs_dir = LOGS_ROOT
    if logs_dir.exists():
        session_log = logs_dir / "session.log"
        if session_log.exists():
            size_kb = session_log.stat().st_size / 1024
            print(f"  📝 Active session log: {size_kb:.2f} KB")
    else:
        print("  📝 'logs/' directory ready for initialization.")

    print("\n" + "=" * 65)
    print(" ✅ DIAGNOSTIC COMPLETE: Review the checks and benchmark above for this environment.")
    print("=" * 65)

if __name__ == "__main__":
    print_banner()
    audit_profiles()
    run_benchmark(50000)
    audit_system()