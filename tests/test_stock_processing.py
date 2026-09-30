import pytest
import pandas as pd
from engine.shared.families import assign_families, assign_family, build_family_rules
from engine.stock_processing.data_processor import calculate_margin

def test_classify_family():
    families = {
        "Category A": ["30", "40"],
        "Category B": ["13", "23"]
    }
    rules = build_family_rules(families)
    assert assign_family("30-ABC", rules) == "Category A"
    assert assign_family("23-XYZ", rules) == "Category B"
    assert assign_family("99-ZZZ", rules) == "Other"
    assert assign_family("99-ZZZ", rules, default_family="Fallback") == "Fallback"

def test_calculate_margin():
    df = pd.DataFrame({
        "Sales": [1000, 2000, 0],
        "Cost": [500, 1500, 500]
    })
    # (Sales value - Cost) / Sales value
    margins = calculate_margin(df, "Sales", "Cost")
    assert margins[0] == 0.50  # 500 / 1000
    assert margins[1] == 0.25  # 500 / 2000
    assert margins[2] == 0.00  # Avoid division by zero


def test_batch_family_classifier_matches_iterative_semantics():
    families = {
        "Generic": ["00", "AB"],
        "Specific": ["ABCD", "ABC"],
        "Duplicate Later": ["AB"],
    }
    rules = build_family_rules(families)
    raw = pd.Series([
        "ABCD-123",
        "00-item",
        "ABC-1",
        "AB-2",
        "REVISAR | UNKNOWN",
        " ABCD-999 ",
        12345,
        None,
    ])

    iterative = raw.apply(
        lambda code: assign_family(code, rules, default_family="Unclassified")
    )
    batched = assign_families(raw, rules, default_family="Unclassified")

    assert batched.equals(iterative)
    # Duplicate equal prefixes keep stable first-rule priority.
    assert batched.iloc[3] == "Generic"
    # Numeric/None inputs and unmatched values share the configured fallback.
    assert batched.iloc[6] == "Unclassified"
    assert batched.iloc[7] == "Unclassified"


@pytest.mark.parametrize("specific_first", [False, True])
def test_longest_family_prefix_is_independent_of_rule_order(specific_first):
    entries = [("Broad", ["AX"]), ("Narrow", ["AXQ"])]
    if specific_first:
        entries.reverse()
    rules = build_family_rules(dict(entries))
    articles = pd.Series(["AXQ-item", "AXQZ-item", "AX-item"])
    expected = ["Narrow", "Narrow", "Broad"]

    assert [assign_family(article, rules) for article in articles] == expected
    assert assign_families(articles, rules).tolist() == expected
