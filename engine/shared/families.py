import re
import pandas as pd
from typing import List, Tuple, Dict
from core.data_sanitizer import clean_sku_series

def build_family_rules(families_dict: Dict[str, List[str]]) -> List[Tuple[str, str]]:
    rules = []
    for family, prefixes in families_dict.items():
        for prefix in prefixes:
            p_str = str(prefix).strip().upper()
            if p_str:
                rules.append((p_str, family))
    rules.sort(key=lambda x: len(x[0]), reverse=True)
    return rules

def assign_family(code, rules: List[Tuple[str, str]]) -> str:
    if pd.isna(code) or not isinstance(code, str):
        return "Other"
    code = str(code).strip().upper()
    if code.startswith("REVISAR"):
        return "REVISAR"
    for prefix, family in rules:
        if code.startswith(prefix):
            return family
    return "Other"

def vectorize_assign_families(series: pd.Series, rules: List[Tuple[str, str]]) -> pd.Series:
    """
    High-performance vector mapping using regex boundary matches.
    """
    clean_series = clean_sku_series(series).str.upper()
    result = pd.Series("Other", index=clean_series.index)
    
    # Flag REVISAR explicitly
    revisar_mask = clean_series.str.startswith("REVISAR")
    result[revisar_mask] = "REVISAR"
    
    unassigned_mask = ~revisar_mask
    for prefix, family in rules:
        if not unassigned_mask.any():
            break
        # Match prefix at the start of string
        pattern = f"^{re.escape(prefix)}"
        matched = clean_series[unassigned_mask].str.contains(pattern, regex=True, na=False)
        matched_indices = matched[matched].index
        if not matched_indices.empty:
            result.loc[matched_indices] = family
            unassigned_mask.loc[matched_indices] = False
            
    return result
