import pandas as pd
from typing import List, Tuple, Dict
from core.data_sanitizer import clean_sku_series

_TRIE_FAMILY_KEY = "__family__"


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


def _build_prefix_trie(rules: List[Tuple[str, str]]) -> dict:
    """Compile ordered prefix rules into a trie while preserving first-rule wins."""
    root = {}
    for prefix, family in rules:
        node = root
        for char in prefix:
            node = node.setdefault(char, {})
        # Equal prefixes preserve the same stable priority as assign_family().
        node.setdefault(_TRIE_FAMILY_KEY, family)
    return root


def _assign_family_from_trie(code: str, trie: dict) -> str:
    if code.startswith("REVISAR"):
        return "REVISAR"

    node = trie
    best_family = None
    for char in code:
        next_node = node.get(char)
        if next_node is None:
            break
        node = next_node
        if _TRIE_FAMILY_KEY in node:
            best_family = node[_TRIE_FAMILY_KEY]

    return best_family if best_family is not None else "Other"


def vectorize_assign_families(series: pd.Series, rules: List[Tuple[str, str]]) -> pd.Series:
    """
    Batch-classify a Series with the exact longest-prefix semantics of assign_family().

    The public name is retained for backward compatibility. Internally a prefix trie
    avoids running one full regex scan per configured prefix.
    """
    clean_series = clean_sku_series(series).str.upper()
    if not rules:
        return pd.Series("Other", index=clean_series.index, dtype="object")

    trie = _build_prefix_trie(rules)
    return clean_series.map(lambda code: _assign_family_from_trie(code, trie))
