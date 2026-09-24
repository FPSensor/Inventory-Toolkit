"""Data preparation for Year-over-Year sales reports."""

import pandas as pd

from engine.shared.families import assign_families


def process_sales_data(
    yoy_file_path,
    yoy_start_dt,
    yoy_end_dt,
    yoy_config,
    family_rules=None,
):
    input_config = yoy_config["input"]
    date_column = input_config["date_column"]
    quantity_column = input_config["quantity_column"]

    dataframe = pd.read_excel(yoy_file_path, sheet_name=0)

    if date_column in dataframe.columns:
        dataframe = dataframe[dataframe[date_column] != date_column]
    dataframe[date_column] = pd.to_datetime(dataframe[date_column], errors="coerce")
    dataframe[quantity_column] = pd.to_numeric(
        dataframe[quantity_column], errors="coerce"
    ).fillna(0)

    if family_rules is not None:
        item_column = input_config["item_column"]
        family_column = input_config["grouping_column"]
        dataframe[family_column] = assign_families(dataframe[item_column], family_rules)

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

    return current_frame, previous_frame, previous_start
