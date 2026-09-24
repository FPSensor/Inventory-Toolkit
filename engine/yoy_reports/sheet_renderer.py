"""Worksheet orchestration for Year-over-Year sales reports."""

from openpyxl.utils import get_column_letter

from core.business_schema import SIZE_COLUMN
from engine.yoy_reports.comparison_renderer import render_yoy_comparison_blocks
from engine.yoy_reports.current_sales_renderer import render_current_sales_block


def render_report_sheet(
    worksheet,
    current_frame,
    previous_frame,
    start_date,
    end_date,
    previous_start,
    yoy_config,
    grouping_column,
    include_sizes=False,
):
    input_config = yoy_config["input"]
    branch_column = input_config["branch_column"]
    quantity_column = input_config["quantity_column"]
    size_column = input_config.get("size_column", SIZE_COLUMN)
    groups = yoy_config["groups"]

    all_branches = list(
        dict.fromkeys(branch for branches in groups.values() for branch in branches)
    )

    current_row = render_current_sales_block(
        worksheet,
        current_frame,
        start_date,
        end_date,
        grouping_column,
        branch_column,
        quantity_column,
        size_column,
        all_branches,
        include_sizes,
    )
    render_yoy_comparison_blocks(
        worksheet,
        current_frame,
        previous_frame,
        start_date,
        end_date,
        previous_start,
        grouping_column,
        branch_column,
        quantity_column,
        groups,
        current_row,
    )

    for column_index in range(1, worksheet.max_column + 1):
        worksheet.column_dimensions[get_column_letter(column_index)].width = 15
    worksheet.column_dimensions["A"].width = 30
