"""Data preparation for Year-over-Year sales reports."""

import pandas as pd

from core.logger import log_debug_event
from engine.shared.families import assign_families
from engine.yoy_reports.metrics import resolve_metric_specs


def process_sales_data(
    yoy_file_path,
    yoy_start_dt,
    yoy_end_dt,
    yoy_config,
    family_rules=None,
    default_family="Other",
    grouping_column=None,
):
    input_config = yoy_config["input"]
    date_column = input_config["date_column"]
    quantity_column = input_config["quantity_column"]
    metric_specs = resolve_metric_specs(yoy_config)

    dataframe = pd.read_excel(yoy_file_path, sheet_name=0)
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
