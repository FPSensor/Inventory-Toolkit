"""Excel rendering for Stock Processing outputs."""

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils.dataframe import dataframe_to_rows

from core.business_schema import (
    COST_COLUMN,
    FAMILY_COLUMN,
    MARGIN_PREFIX,
    SALES_VALUE_LABEL,
    UNIT_COST_PREFIX,
    UNIT_SALES_PREFIX,
)
from core.runtime.logger import log, log_debug_event
from core.files.system_utils import safe_openpyxl_save
from engine.stock_processing.data_processor import calculate_margin

MAX_COLUMN_WIDTH = 50


def apply_excel_formatting(worksheet, is_summary=False, column_formats=None):
    column_formats = column_formats or {}
    header_fill = PatternFill(
        start_color="D9D9D9",
        end_color="D9D9D9",
        fill_type="solid",
    )
    header_font = Font(bold=True)
    for cell in worksheet[1]:
        cell.font = header_font
        cell.fill = header_fill

    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions

    for column_cells in worksheet.columns:
        max_length = 0
        column_letter = column_cells[0].column_letter

        for cell in column_cells:
            value_length = len(str(cell.value)) if cell.value is not None else 0
            max_length = max(max_length, value_length)
            if cell.row <= 1 or cell.value is None:
                continue

            if cell.column in column_formats:
                cell.number_format = column_formats[cell.column]
            elif isinstance(cell.value, (int, float)) and not is_summary:
                cell.number_format = "#,##0"

        worksheet.column_dimensions[column_letter].width = min(
            max_length + 2,
            MAX_COLUMN_WIDTH,
        )


def build_summary(
    stock_frame,
    summary,
    family_column,
    *,
    cost_factor=1.0,
    hidden_families=(),
    totals_label="",
    blank_undefined_margin=False,
    quantity_format="#,##0",
):
    """Aggregate one configured summary and describe its value formats.

    Standard reports show a zero margin when sales are not positive. Template
    reports follow PivotTable arithmetic instead, so both sheets agree: any
    nonzero sales value has a margin and only a zero one is left blank.
    """
    entities = [entity for entity in summary.get("entities", []) if entity in stock_frame.columns]
    values = [
        column
        for entity in entities
        for column in (entity, f"{entity}.{COST_COLUMN}", f"{entity}.{SALES_VALUE_LABEL}")
        if column in stock_frame.columns
    ]
    visible = stock_frame[~stock_frame[family_column].isin(hidden_families)]
    frame = visible.groupby(family_column).agg({column: "sum" for column in values}).reset_index()
    if totals_label:
        total = {family_column: totals_label, **frame[values].sum().to_dict()}
        frame = pd.concat([frame, pd.DataFrame([total])], ignore_index=True)

    export_columns = [family_column]
    column_formats = {}
    for entity in entities:
        cost_column = f"{entity}.{COST_COLUMN}"
        sales_column = f"{entity}.{SALES_VALUE_LABEL}"
        if quantity_format != "#,##0":
            column_formats[len(export_columns) + 1] = quantity_format
        if sales_column not in frame.columns or cost_column not in frame.columns:
            export_columns.append(entity)
            continue
        margin_column = f"{MARGIN_PREFIX}{entity}"
        if blank_undefined_margin:
            sales = frame[sales_column].astype(float).replace(0, np.nan)
            frame[margin_column] = 1 - frame[cost_column] * cost_factor / sales
        else:
            frame[margin_column] = calculate_margin(frame, sales_column, cost_column, cost_factor)
        first_value_column = len(export_columns) + 2
        column_formats[first_value_column] = "#,##0.00"
        column_formats[first_value_column + 1] = "#,##0.00"
        column_formats[first_value_column + 2] = "0.00%"
        export_columns.extend([entity, cost_column, sales_column, margin_column])

    frame = frame[export_columns]
    titles = summary.get("titles", [])
    if titles and len(titles) == len(frame.columns):
        frame.columns = titles
    else:
        log.warning(
            "Title mismatch in sheet %s. Original names will be used.",
            summary.get("sheet_name", "Summary"),
        )
    return frame, column_formats


def render_stock_without_cost(output_file, frame, sheet_name, stores, quantity_format="#,##0", on_locked=None):
    """Save the list of stock without cost as its own workbook."""
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = sheet_name[:31]
    for row in dataframe_to_rows(frame, index=False, header=True):
        worksheet.append(row)
    formats = {
        index: "#,##0.00" if str(column).endswith(f".{SALES_VALUE_LABEL}") else quantity_format
        for index, column in enumerate(frame.columns, 1)
        if column in stores or str(column).endswith(f".{SALES_VALUE_LABEL}")
    }
    apply_excel_formatting(worksheet, is_summary=True, column_formats=formats)
    return safe_openpyxl_save(workbook, output_file, on_locked=on_locked)


def render_stock_excel(
    output_file,
    stock_frame,
    summaries,
    stock_columns,
    raw_data_sheet,
    family_column=FAMILY_COLUMN,
    on_locked=None,
    quantity_format="#,##0",
    quantity_columns=(),
    cost_factor=1.0,
    hidden_families=(),
    totals_label="",
):
    log.info("Generating dynamic reports and applying formats...")
    log_debug_event(
        "stock_render_start",
        output_file=output_file,
        data_shape=stock_frame.shape,
        summary_count=len(summaries),
        raw_data_sheet=raw_data_sheet,
    )
    workbook = Workbook()
    workbook.remove(workbook.active)

    for summary in summaries:
        sheet_name = summary.get("sheet_name", "Summary")
        included_entities = summary.get("entities", [])

        valid_entities = [entity for entity in included_entities if entity in stock_columns]
        if not valid_entities:
            log_debug_event(
                "stock_summary_skipped",
                sheet_name=sheet_name,
                requested_entities=included_entities,
                reason="no_entities_present",
            )
            continue

        log_debug_event(
            "stock_summary_render",
            sheet_name=sheet_name,
            requested_entities=included_entities,
            valid_entities=valid_entities,
        )
        worksheet = workbook.create_sheet(sheet_name)
        summary_frame, column_formats = build_summary(
            stock_frame, summary, family_column, cost_factor=cost_factor,
            hidden_families=hidden_families, totals_label=totals_label,
            quantity_format=quantity_format,
        )

        for row in dataframe_to_rows(summary_frame, index=False, header=True):
            worksheet.append(row)
        apply_excel_formatting(worksheet, is_summary=True, column_formats=column_formats)
        log_debug_event(
            "stock_summary_ready",
            sheet_name=sheet_name,
            row_count=worksheet.max_row,
            column_count=worksheet.max_column,
        )

    data_worksheet = workbook.create_sheet(raw_data_sheet)
    for row in dataframe_to_rows(stock_frame, index=False, header=True):
        data_worksheet.append(row)
    raw_formats = {
        index: "#,##0.00"
        for index, column in enumerate(stock_frame.columns, 1)
        if str(column).endswith((f".{COST_COLUMN}", f".{SALES_VALUE_LABEL}"))
        or str(column).startswith((UNIT_COST_PREFIX, UNIT_SALES_PREFIX))
    }
    raw_formats.update({index: quantity_format for index, column in enumerate(stock_frame.columns, 1) if column in quantity_columns})
    apply_excel_formatting(data_worksheet, is_summary=False, column_formats=raw_formats)
    log_debug_event(
        "stock_raw_sheet_ready",
        sheet_name=raw_data_sheet,
        row_count=data_worksheet.max_row,
        column_count=data_worksheet.max_column,
    )
    final_path = safe_openpyxl_save(workbook, output_file, on_locked=on_locked)
    log_debug_event(
        "stock_render_saved",
        output_file=final_path,
        sheets=list(workbook.sheetnames),
    )
    return final_path
