"""Category selection is a profile decision, independent of product prefixes."""
from types import SimpleNamespace

import pandas as pd
import pytest

from engine.stock_processing.contracts import INTERNAL_ARTICLE_COLUMN, INTERNAL_FAMILY_COLUMN
from engine.stock_processing.data_processor import classify_stock_families, prepare_stock_frame


@pytest.mark.parametrize("mode, expected", [
    ("column", ["Fresh", "Other", "Other"]),
    ("rules", ["Prefix", "Other", "Other"]),
    ("none", ["Other", "Other", "Other"]),
])
def test_category_sources_are_explicit(mode, expected):
    frame = pd.DataFrame({INTERNAL_ARTICLE_COLUMN: ["AB1", "CD2", "EF3"],
                          "Source category": [" Fresh ", None, " "]})
    result = classify_stock_families(frame, [("AB", "Prefix")], default_family="Other",
        source_column="Source category" if mode == "column" else None, use_rules=mode == "rules")
    assert result[INTERNAL_FAMILY_COLUMN].tolist() == expected
    assert INTERNAL_FAMILY_COLUMN not in frame


def test_missing_source_category_is_not_silently_reclassified():
    plan = SimpleNamespace(input={"family_mode": "column", "family_column": "Source category"},
        article_column="SKU", drop_columns=(), text_columns=(), numeric_columns=(),
        active_stores=("Counter",), stock_database_columns={})
    with pytest.raises(ValueError, match="category"):
        prepare_stock_frame(pd.DataFrame({"SKU": ["AB1"], "Counter": [2]}), plan)
