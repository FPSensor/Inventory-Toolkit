"""Family classification helpers shared by all processing engines."""

from typing import Dict, List, Tuple

import pandas as pd

from core.business_schema import REVIEW_FAMILY
from core.data_sanitizer import clean_sku_series

_TRIE_FAMILY_KEY = "__family__"
_DEFAULT_UNMATCHED_FAMILY = "Other"


def build_family_rules(family_map: Dict[str, List[str]]) -> List[Tuple[str, str]]:
    rules = []
    for family, prefixes in family_map.items():
        for prefix in prefixes:
            normalized_prefix = str(prefix).strip().upper()
            if normalized_prefix:
                rules.append((normalized_prefix, family))
    rules.sort(key=lambda rule: len(rule[0]), reverse=True)
    return rules


def assign_family(code, rules: List[Tuple[str, str]]) -> str:
    if pd.isna(code) or not isinstance(code, str):
        return _DEFAULT_UNMATCHED_FAMILY

    normalized_code = str(code).strip().upper()
    if normalized_code.startswith(REVIEW_FAMILY):
        return REVIEW_FAMILY

    for prefix, family in rules:
        if normalized_code.startswith(prefix):
            return family
    return _DEFAULT_UNMATCHED_FAMILY


def _build_prefix_trie(rules: List[Tuple[str, str]]) -> dict:
    """Compile ordered prefix rules into a trie while preserving first-rule wins."""
    root = {}
    for prefix, family in rules:
        node = root
        for character in prefix:
            node = node.setdefault(character, {})
        # Equal prefixes keep the same stable priority as assign_family().
        node.setdefault(_TRIE_FAMILY_KEY, family)
    return root


def _assign_family_from_trie(code: str, trie: dict) -> str:
    if code.startswith(REVIEW_FAMILY):
        return REVIEW_FAMILY

    node = trie
    best_family = None
    for character in code:
        next_node = node.get(character)
        if next_node is None:
            break
        node = next_node
        if _TRIE_FAMILY_KEY in node:
            best_family = node[_TRIE_FAMILY_KEY]

    return best_family if best_family is not None else _DEFAULT_UNMATCHED_FAMILY


def assign_families(series: pd.Series, rules: List[Tuple[str, str]]) -> pd.Series:
    """Batch-classify a Series with the exact semantics of ``assign_family``."""
    clean_series = clean_sku_series(series).str.upper()
    if not rules:
        return pd.Series(_DEFAULT_UNMATCHED_FAMILY, index=clean_series.index, dtype="object")

    trie = _build_prefix_trie(rules)
    return clean_series.map(lambda code: _assign_family_from_trie(code, trie))


# Public compatibility alias retained for integrations written before the trie
# implementation was renamed to describe what it does rather than how it works.
vectorize_assign_families = assign_families
