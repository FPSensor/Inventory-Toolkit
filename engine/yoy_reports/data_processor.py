"""Data preparation for Year-over-Year sales reports."""

import re

import pandas as pd

from core.logger import log_debug_event
from core.business_schema import UNMATCHED_FAMILY
from engine.shared.families import assign_families
from engine.yoy_reports.metrics import resolve_metric_specs


def _exported_number(value):
    """Read a figure from a totals row, which exports store as localized text."""
    text = str(value).strip()
    if not re.fullmatch(r"-?\d{1,3}(\.\d{3})*(,\d+)?|-?\d+(,\d+)?", text):
        return None
    return float(text.replace(".", "").replace(",", "."))


def check_exported_totals(dataframe, input_config):
    """Verify and drop the totals row some systems append to a sales export.

    The row identifies itself: no item or location, and figures stored as text.
    A mismatch means rows were lost, added or could not be read as numbers.
    """
    identity = [input_config["item_column"], input_config["branch_column"]]
    figures = [
        column for column in (input_config["quantity_column"], input_config.get("sales_column"))
        if column in dataframe.columns
    ]
    if dataframe.empty or not figures or any(column not in dataframe.columns for column in identity):
        return dataframe
    last = dataframe.iloc[-1]
    if last[identity].notna().any() or not all(isinstance(last[column], str) for column in figures):
        return dataframe
    rows = dataframe.iloc[:-1]
    for column in figures:
        expected = _exported_number(last[column])
        if expected is None:
            return dataframe
        found = pd.to_numeric(rows[column], errors="coerce").fillna(0).sum()
        if abs(found - expected) > 0.01:
            raise ValueError(
                f"Sales file totals do not match: '{column}' adds up to {found:,.2f} but the file's own total "
                f"row says {expected:,.2f}. Export the file again, or remove the total row if you edited it on purpose."
            )
    log_debug_event("yoy_exported_totals_verified", rows=len(rows), columns=figures)
    return rows


def process_sales_data(
    yoy_file_path,
    yoy_start_dt,
    yoy_end_dt,
    yoy_config,
    family_rules=None,
    default_family=UNMATCHED_FAMILY,
    grouping_column=None,
):
    input_config = yoy_config["input"]
    date_column = input_config["date_column"]
    quantity_column = input_config["quantity_column"]
    metric_specs = resolve_metric_specs(yoy_config)

    text_columns = {input_config[key]: str for key in ("item_column", "branch_column", "variant_column") if input_config.get(key)}
    dataframe = pd.read_excel(yoy_file_path, sheet_name=0, dtype=text_columns)
    log_debug_event(
        "yoy_input_loaded",
        file_path=yoy_file_path,
        shape=dataframe.shape,
        columns=list(dataframe.columns),
        date_column=date_column,
        quantity_column=quantity_column,
    )

    if date_column in dataframe.columns:
        dataframe = dataframe[dataframe[date_column] != date_column]
    dataframe = check_exported_totals(dataframe, input_config)
    if input_config.get("code_tokenization", "whole") == "first_token":
        for column in (input_config["item_column"], input_config.get("variant_column")):
            if column in dataframe.columns:
                dataframe = dataframe.assign(**{column: dataframe[column].str.split().str[0]})
    aliases = input_config.get("branch_aliases") or {}
    branch_column = input_config["branch_column"]
    if aliases and branch_column in dataframe.columns:
        dataframe = dataframe.assign(
            **{branch_column: dataframe[branch_column].str.strip().replace(aliases)}
        )
    resolved_grouping_column = grouping_column or input_config["grouping_column"]
    grouping_source_column = (
        input_config["item_column"] if family_rules is not None else resolved_grouping_column
    )
    required_columns = {
        date_column,
        input_config["branch_column"],
        grouping_source_column,
        *(metric.column for metric in metric_specs),
    }
    if yoy_config["output"].get("include_variants", False):
        required_columns.add(input_config["variant_column"])
    missing_columns = sorted(column for column in required_columns if column not in dataframe.columns)
    if missing_columns:
        raise ValueError(f"YoY input is missing required columns: {missing_columns}")

    dataframe[date_column] = pd.to_datetime(dataframe[date_column], errors="coerce")
    for metric in metric_specs:
        dataframe[metric.column] = pd.to_numeric(
            dataframe[metric.column], errors="coerce"
        ).fillna(0)

    if family_rules is not None:
        item_column = input_config["item_column"]
        family_column = input_config["grouping_column"]
        dataframe[family_column] = assign_families(
            dataframe[item_column],
            family_rules,
            default_family=default_family,
        )
        log_debug_event(
            "yoy_dynamic_family_assignment",
            family_rule_count=len(family_rules),
            family_count=int(dataframe[family_column].nunique(dropna=False)),
        )

    previous_start = yoy_start_dt - pd.DateOffset(years=1)
    previous_end = yoy_end_dt - pd.DateOffset(years=1)

    current_frame = dataframe[
        (dataframe[date_column] >= yoy_start_dt)
        & (dataframe[date_column] <= yoy_end_dt)
    ].copy()
    previous_frame = dataframe[
        (dataframe[date_column] >= previous_start)
        & (dataframe[date_column] <= previous_end)
    ].copy()
    log_debug_event(
        "yoy_period_filter",
        total_rows=len(dataframe),
        current_rows=len(current_frame),
        previous_rows=len(previous_frame),
        current_start=str(yoy_start_dt),
        current_end=str(yoy_end_dt),
        previous_start=str(previous_start),
        previous_end=str(previous_end),
        invalid_dates=int(dataframe[date_column].isna().sum()),
    )

    return current_frame, previous_frame, previous_start
