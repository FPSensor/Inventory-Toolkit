"""Data preparation for Year-over-Year sales reports."""

import re

import pandas as pd

from core.runtime.logger import log_debug_event
from core.business_schema import UNMATCHED_FAMILY
from core.files.table_reader import parse_dates, read_table
from engine.shared.families import assign_families
from engine.yoy_reports.metrics import resolve_metric_specs


def _exported_numbers(value):
    """Return every reading of a figure that exports store as localized text.

    ``1.234`` is a thousand in some countries and a fraction in others, so both
    are offered and the data decides which one the file uses.
    """
    if not isinstance(value, str):
        return [] if pd.isna(value) else [float(value)]
    text = value.strip()
    readings = set()
    for thousands, decimal in ((".", ","), (",", ".")):
        pattern = rf"-?(\d{{1,3}}({re.escape(thousands)}\d{{3}})+|\d+)({re.escape(decimal)}\d+)?"
        if re.fullmatch(pattern, text):
            readings.add(float(text.replace(thousands, "").replace(decimal, ".")))
    return sorted(readings)


def check_exported_totals(dataframe, input_config):
    """Verify and drop the totals row some systems append to a sales export.

    The row identifies itself: no item or location, and either figures stored as
    text or no date.
    A mismatch means rows were lost, added or could not be read as numbers.
    """
    identity = [input_config["item_column"], input_config["branch_column"]]
    figures = [
        column for column in (
            input_config["quantity_column"],
            # Adding up unit prices says nothing about the file.
            None if input_config.get("sales_values") == "unit_price" else input_config.get("sales_column"),
        )
        if column in dataframe.columns
    ]
    if dataframe.empty or not figures or any(column not in dataframe.columns for column in identity):
        return dataframe
    last = dataframe.iloc[-1]
    is_text = all(isinstance(last[column], str) for column in figures)
    has_date = pd.notna(pd.to_datetime(last.get(input_config["date_column"]), errors="coerce", format="mixed"))
    if last[identity].notna().any() or (has_date and not is_text):
        return dataframe
    rows = dataframe.iloc[:-1]
    for column in figures:
        expected = _exported_numbers(last[column])
        if not expected:
            return dataframe
        found = pd.to_numeric(rows[column], errors="coerce").fillna(0).sum()
        if all(abs(found - reading) > 0.01 for reading in expected):
            raise ValueError(
                f"Sales file totals do not match: '{column}' adds up to {found:,.2f} but the file's own total "
                f"row says {last[column]}. Export the file again, or remove the total row if you edited it on purpose."
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
    on_notice=None,
):
    input_config = yoy_config["input"]
    date_column = input_config["date_column"]
    quantity_column = input_config["quantity_column"]
    metric_specs = resolve_metric_specs(yoy_config)

    text_columns = [input_config[key] for key in ("item_column", "branch_column", "variant_column") if input_config.get(key)]
    # Keep figures as stored: a localized total such as "1.234" must not be
    # converted before it is compared with the rows.
    figures = [input_config[key] for key in ("quantity_column", "sales_column") if input_config.get(key)]
    dataframe = read_table(
        yoy_file_path, text=text_columns, as_stored=figures,
        all_sheets=input_config.get("all_sheets", False), on_notice=on_notice,
    )
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

    dataframe = dataframe.copy()
    dataframe[date_column] = parse_dates(dataframe[date_column])
    undated = int(dataframe[date_column].isna().sum())
    if undated and on_notice:
        on_notice(f"{undated:,} sales rows have no readable date and were not counted.")
    for metric in metric_specs:
        dataframe[metric.column] = pd.to_numeric(
            dataframe[metric.column], errors="coerce"
        ).fillna(0)
    sales_column = input_config.get("sales_column")
    if input_config.get("sales_values") == "unit_price" and sales_column in dataframe.columns:
        quantities = pd.to_numeric(dataframe[quantity_column], errors="coerce").fillna(0)
        prices = pd.to_numeric(dataframe[sales_column], errors="coerce").fillna(0)
        dataframe[sales_column] = quantities * prices

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
