"""Workbook orchestration for Year-over-Year sales report exports."""

import openpyxl
import pandas as pd

from core.system_utils import safe_openpyxl_save
from engine.yoy_reports.sheet_renderer import render_report_sheet


def render_yoy_sales_excel(
    output_path,
    current_frame,
    previous_frame,
    start_date,
    end_date,
    previous_start,
    yoy_config,
    grouping_column,
    segmented,
    include_sizes=False,
    interactive=True,
):
    workbook = openpyxl.Workbook()
    workbook.remove(workbook.active)

    date_column = yoy_config["input"]["date_column"]
    clean_current_frame = (
        current_frame.dropna(subset=[date_column])
        if date_column in current_frame.columns
        else current_frame
    )

    if segmented and not clean_current_frame.empty:
        periods = sorted(clean_current_frame[date_column].dt.to_period("M").unique())
        for period in periods:
            current_mask = current_frame[date_column].dt.to_period("M") == period
            period_current = current_frame[current_mask]

            previous_period = (
                period.to_timestamp() - pd.DateOffset(years=1)
            ).to_period("M")
            previous_mask = previous_frame[date_column].dt.to_period("M") == previous_period
            period_previous = previous_frame[previous_mask]

            worksheet = workbook.create_sheet(title=period.strftime("%m-%y"))
            period_start = period_current[date_column].min()
            period_end = period_current[date_column].max()
            if pd.isna(period_start):
                period_start = start_date
            if pd.isna(period_end):
                period_end = end_date
            period_previous_start = period_start - pd.DateOffset(years=1)

            render_report_sheet(
                worksheet,
                period_current,
                period_previous,
                period_start,
                period_end,
                period_previous_start,
                yoy_config,
                grouping_column,
                include_sizes,
            )

    span_days = (end_date - start_date).days
    if span_days > 366 and not clean_current_frame.empty:
        years = sorted(clean_current_frame[date_column].dt.year.unique())
        for year in years:
            current_year_frame = current_frame[current_frame[date_column].dt.year == year]
            previous_year_frame = previous_frame[
                previous_frame[date_column].dt.year == (year - 1)
            ]
            worksheet = workbook.create_sheet(title=f"Full {year}")

            year_start = current_year_frame[date_column].min()
            year_end = current_year_frame[date_column].max()
            if pd.isna(year_start):
                year_start = start_date
            if pd.isna(year_end):
                year_end = end_date
            year_previous_start = year_start - pd.DateOffset(years=1)

            render_report_sheet(
                worksheet,
                current_year_frame,
                previous_year_frame,
                year_start,
                year_end,
                year_previous_start,
                yoy_config,
                grouping_column,
                include_sizes,
            )
    else:
        sheet_title = "Full Report" if segmented else "Sales"
        worksheet = workbook.create_sheet(title=sheet_title)
        render_report_sheet(
            worksheet,
            current_frame,
            previous_frame,
            start_date,
            end_date,
            previous_start,
            yoy_config,
            grouping_column,
            include_sizes,
        )

    if not workbook.sheetnames:
        worksheet = workbook.create_sheet(title="Sales")
        render_report_sheet(
            worksheet,
            current_frame,
            previous_frame,
            start_date,
            end_date,
            previous_start,
            yoy_config,
            grouping_column,
            include_sizes,
        )

    return safe_openpyxl_save(workbook, output_path, interactive=interactive)
