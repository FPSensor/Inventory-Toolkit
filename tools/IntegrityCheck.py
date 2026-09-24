import sys
import os
from pathlib import Path
import math

# Link project root directory
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import numpy as np

from core.configuration_manager import ConfigurationManager
from core.data_sanitizer import clean_sku_series, sanitize_dataframe
from engine.shared.families import build_family_rules, assign_family, vectorize_assign_families
from engine.inventory_cross_check.data_processor import normalize_article, calculate_difference
from engine.stock_processing.data_processor import calculate_margin, process_pricing
from engine.yoy_reports.data_processor import process_sales_data

class IntegrityAuditor:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.details = []

    def assert_check(self, name: str, condition: bool, err_msg: str = ""):
        if condition:
            self.passed += 1
            print(f"  ✅ [PASS] {name}")
        else:
            self.failed += 1
            print(f"  ❌ [FAIL] {name} -> {err_msg}")
            self.details.append(f"FAIL: {name} | {err_msg}")

    def warn_check(self, name: str, condition: bool, warn_msg: str = ""):
        if condition:
            self.passed += 1
            print(f"  ✅ [PASS] {name}")
        else:
            self.warnings += 1
            print(f"  ⚠️ [WARN] {name} -> {warn_msg}")
            self.details.append(f"WARN: {name} | {warn_msg}")

    def run_all(self):
        print("=" * 70)
        print(" 🛡️ INVENTORY TOOLKIT — DEEP LOGICAL & NUMERICAL INTEGRITY AUDIT")
        print("=" * 70)

        self.audit_sku_sanitization()
        self.audit_prefix_matching_and_family_resolution()
        self.audit_inventory_cross_check_math()
        self.audit_stock_processing_margins_and_pricing()
        self.audit_yoy_time_series_offsets()
        self.audit_e2e_simulation_with_real_profile()

        print("\n" + "=" * 70)
        print(f" 📊 RESULTS: {self.passed} Passed | {self.failed} Failed | {self.warnings} Warnings")
        if self.failed == 0:
            print(" ✅ All implemented integrity checks passed; no regressions were detected by this audit.")
        else:
            print(" ⚠️ ATTENTION: Critical integrity failures detected:")
            for d in self.details:
                print(f"   • {d}")
        print("=" * 70)

    # -------------------------------------------------------------------------
    # 1. SKU SANITIZATION & DIRTY EXCEL ARTIFACTS
    # -------------------------------------------------------------------------
    def audit_sku_sanitization(self):
        print("\n🧹 [1/6] Auditing SKU Sanitization and Corrupted Inputs...")
        raw_series = pd.Series([
            "00100-151",
            "12060-142.0",       # Excel float conversion artifact
            "  0085-99   ",       # Leading/trailing whitespace
            np.nan,               # Real NaN/Nulls
            "None",               # Literal 'None' string
            104050,               # Raw integers
            "0045-12.0"
        ])

        cleaned = clean_sku_series(raw_series)
        
        self.assert_check("Removal of accidental '.0' suffix", cleaned[1] == "12060-142", f"Got: '{cleaned[1]}'")
        self.assert_check("Trimming of leading/trailing whitespace", cleaned[2] == "0085-99", f"Got: '{cleaned[2]}'")
        self.assert_check("Safe conversion of NaN to empty string", cleaned[3] == "", f"Got: '{cleaned[3]}'")
        self.assert_check("Safe conversion of literal 'None' to empty string", cleaned[4] == "", f"Got: '{cleaned[4]}'")
        self.assert_check("Transparent integer to string casting", cleaned[5] == "104050", f"Got: '{cleaned[5]}'")
        self.assert_check("Compound code '.0' cleanup", cleaned[6] == "0045-12", f"Got: '{cleaned[6]}'")

    # -------------------------------------------------------------------------
    # 2. LONGEST-PREFIX MATCHING & FAMILY RESOLUTION
    # -------------------------------------------------------------------------
    def audit_prefix_matching_and_family_resolution(self):
        print("\n🔍 [2/6] Auditing Longest-Prefix Priority & Family Resolution...")
        
        families_dict = {
            "Buzos": ["008", "08"],
            "Buzos Con Capucha": ["0085", "185", "085"],  # More specific (4 chars)
            "Remeras": ["001", "002"],
            "Accesorios": ["30"]
        }
        rules = build_family_rules(families_dict)

        # Invariant 1: Rules must always be sorted descending by prefix length
        lengths = [len(r[0]) for r in rules]
        is_sorted_desc = all(lengths[i] >= lengths[i+1] for i in range(len(lengths)-1))
        self.assert_check("Rules sorted by descending length O(n)", is_sorted_desc)

        # Invariant 2: '0085-XYZ' must match 'Buzos Con Capucha', NEVER be swallowed by '008' ('Buzos')
        sku_test = "0085-123"
        fam_assigned = assign_family(sku_test, rules)
        self.assert_check("Longest prefix priority resolution (0085 vs 008)", fam_assigned == "Buzos Con Capucha", f"Got: {fam_assigned}")

        # Invariant 3: Vectorized vs Iterative must return EXACT identical results
        test_skus = pd.Series(["0085-A", "008-B", "001-C", "999-Unknown", "REVISAR | Corrupt"])
        res_iter = test_skus.apply(lambda x: assign_family(x, rules))
        res_vec = vectorize_assign_families(test_skus, rules)
        self.assert_check("Exact parity: Vectorized == Iterative", (res_iter == res_vec).all())

        # Invariant 4: Physical count normalization against Master Base
        master_base = ["0085-100", "0085-100-M", "00100-XL"]
        master_set = set(master_base)
        
        self.assert_check("Exact match in Master Base", normalize_article("0085-100", master_base, master_set) == "0085-100")
        self.assert_check("Longest matching prefix available", normalize_article("0085-100-M-RED", master_base, master_set) == "0085-100-M")
        self.assert_check("Unmatched item marked as REVISAR", normalize_article("99999-NOPE", master_base, master_set) == "REVISAR | 99999-NOPE")

    # -------------------------------------------------------------------------
    # 3. INVENTORY CROSS CHECK MATHEMATICS (DIFFERENCES & TOTALS)
    # -------------------------------------------------------------------------
    def audit_inventory_cross_check_math(self):
        print("\n🧮 [3/6] Auditing Cross Check Arithmetic (Differences & Valuations)...")

        # Boundary checks for calculate_difference
        self.assert_check("Standard shortage calculation (Stock: 10 vs Count: 7 -> -3)", calculate_difference(10, 7) == -3)
        self.assert_check("Standard surplus calculation (Stock: 5 vs Count: 8 -> +3)", calculate_difference(5, 8) == 3)
        self.assert_check("Negative system stock handling (-5 vs Count: 2 -> 2)", calculate_difference(-5, 2) == 2, f"Got: {calculate_difference(-5, 2)}")
        self.assert_check("Zero state baseline (0 stock, 0 count -> 0)", calculate_difference(0, 0) == 0)

        # Monetary Float Precision (CTOTAL & VTOTAL)
        diff = -3
        cost = 1999.99
        price = 3499.50
        ctotal = diff * cost
        vtotal = diff * price
        
        self.assert_check("CTOTAL exact currency calculation", math.isclose(ctotal, -5999.97, abs_tol=1e-4), f"CTOTAL: {ctotal}")
        self.assert_check("VTOTAL exact currency calculation", math.isclose(vtotal, -10498.50, abs_tol=1e-4), f"VTOTAL: {vtotal}")

    # -------------------------------------------------------------------------
    # 4. STOCK PROCESSING MATHEMATICS (MARGINS & PRICING)
    # -------------------------------------------------------------------------
    def audit_stock_processing_margins_and_pricing(self):
        print("\n📈 [4/6] Auditing Margin Formulas & Zero-Division Protections...")

        df_mock = pd.DataFrame({
            "Venta": [1000.0, 2000.0, 0.0, -500.0, 1500.0],
            "Costo": [500.0,  1500.0, 300.0, 200.0,  1500.0]
        })

        margins = calculate_margin(df_mock, "Venta", "Costo")

        self.assert_check("Standard 50% margin ((1000-500)/1000)", math.isclose(margins[0], 0.50, abs_tol=1e-4))
        self.assert_check("Standard 25% margin ((2000-1500)/2000)", math.isclose(margins[1], 0.25, abs_tol=1e-4))
        self.assert_check("Zero-Division Protection (Venta=0 -> Margin=0.0)", margins[2] == 0.0, f"Got: {margins[2]}")
        self.assert_check("Negative Price Protection (Venta <= 0 -> Margin=0.0)", margins[3] == 0.0, f"Got: {margins[3]}")
        self.assert_check("Zero Margin Baseline (Venta == Costo -> 0%)", margins[4] == 0.0)

    # -------------------------------------------------------------------------
    # 5. TIME SERIES & OFFSET INTEGRITY (YOY SALES)
    # -------------------------------------------------------------------------
    def audit_yoy_time_series_offsets(self):
        print("\n📅 [5/6] Auditing YoY Sales Date Offsets...")

        start_dt = pd.to_datetime("2026-03-15")
        end_dt = pd.to_datetime("2026-03-31 23:59:59")

        start_prev = start_dt - pd.DateOffset(years=1)
        end_prev = end_dt - pd.DateOffset(years=1)

        self.assert_check("Accurate Start Date 1-year offset", start_prev.year == 2025 and start_prev.month == 3 and start_prev.day == 15)
        self.assert_check("Accurate End Date 1-year offset", end_prev.year == 2025 and end_prev.month == 3 and end_prev.day == 31)

        leap_dt = pd.to_datetime("2024-02-29")
        leap_prev = leap_dt - pd.DateOffset(years=1)
        self.assert_check("Safe Leap Year offset resolution (2024-02-29 -> 2023-02-28)", leap_prev.month == 2 and leap_prev.day == 28)

    # -------------------------------------------------------------------------
    # 6. END-TO-END PROFILE SIMULATION (DEMO)
    # -------------------------------------------------------------------------
    def audit_e2e_simulation_with_real_profile(self):
        print("\n🚀 [6/6] End-to-End simulation with active profile configs...")
        
        try:
            cm = ConfigurationManager(profile="demo")
            familias = cm.get_familias()
            self.assert_check("Successful families load from 'demo' profile", isinstance(familias, dict) and len(familias) > 0)

            stores = cm.get_stores()
            self.assert_check("Active stores loading", "locales_activos" in stores and len(stores["locales_activos"]) > 0)

            cleaning = cm.get_cleaning_rules()
            self.assert_check("Cleaning rules loading", "columnas_texto_a_limpiar" in cleaning)

            df_test = pd.DataFrame({
                "Artículo": [" 00100 ", "00850.0"],
                "CENTRAL": [10, 20],
                "Ignore_Col": ["X", "Y"]
            })
            
            for col in cleaning.get("columnas_texto_a_limpiar", []):
                if col in df_test.columns:
                    df_test[col] = clean_sku_series(df_test[col])

            self.assert_check("E2E Profile-driven SKU sanitization", df_test["Artículo"].iloc[0] == "00100" and df_test["Artículo"].iloc[1] == "00850")

        except Exception as e:
            self.assert_check("ConfigurationManager execution without exceptions", False, str(e))

if __name__ == "__main__":
    auditor = IntegrityAuditor()
    auditor.run_all()