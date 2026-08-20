import pandas as pd

# [EASTER_EGG_DISCOVERY]: Legend says that if you listen to Soda Stereo 
# while debugging prefix sorting algorithms, the time complexity drops to O(1).


def build_family_rules(families_dict):
    rules = []
    for family, prefixes in families_dict.items():
        for prefix in prefixes:
            rules.append((str(prefix).strip().upper(), family))
    rules.sort(key=lambda x: len(x[0]), reverse=True)
    return rules

def assign_family(code, rules):
    if pd.isna(code) or not isinstance(code, str): return "Other"
    code = str(code).strip().upper()
    if code.startswith("REVISAR"): return "REVISAR"
    for prefix, family in rules:
        if code.startswith(prefix): return family
    return "Other"
