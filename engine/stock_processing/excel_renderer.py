"""Excel rendering for Stock Processing outputs."""

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils.dataframe import dataframe_to_rows

from core.business_schema import COST_COLUMN, FAMILY_COLUMN, MARGIN_PREFIX, SALES_VALUE_LABEL
from core.logger import log
from core.system_utils import safe_openpyxl_save
from engine.stock_processing.data_processor import calculate_margin

MAX_COLUMN_WIDTH = 50


def apply_excel_formatting(worksheet, is_summary=False):
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
        column_name = str(worksheet[f"{column_letter}1"].value).upper()

        for cell in column_cells:
            value_length = len(str(cell.value)) if cell.value is not None else 0
            max_length = max(max_length, value_length)
            if cell.row <= 1 or cell.value is None:
                continue

            if "MARGEN" in column_name:
                cell.number_format = "0.00%"
            elif "COSTO" in column_name or "VENTA" in column_name or "TOTAL" in column_name:
                cell.number_format = "#,##0.00"
            elif isinstance(cell.value, (int, float)) and not is_summary:
                cell.number_format = "#,##0"

        worksheet.column_dimensions[column_letter].width = min(
            max_length + 2,
            MAX_COLUMN_WIDTH,
        )


def render_stock_excel(
    output_file,
    stock_frame,
    summaries,
    stock_columns,
    raw_data_sheet,
    interactive=True,
):
    log.info("Generating dynamic reports and applying formats...")
    workbook = Workbook()
    workbook.remove(workbook.active)

    for summary in summaries:
        sheet_name = summary.get("sheet_name", "Summary")
        included_entities = summary.get("entities", [])
        final_titles = summary.get("titles", [])

        valid_entities = [entity for entity in included_entities if entity in stock_columns]
        if not valid_entities:
            continue

        worksheet = workbook.create_sheet(sheet_name)
        aggregations = {}
        for entity in valid_entities:
            aggregations[entity] = "sum"
            cost_column = f"{entity}.{COST_COLUMN}"
            sales_column = f"{entity}.{SALES_VALUE_LABEL}"
            if cost_column in stock_columns:
                aggregations[cost_column] = "sum"
            if sales_column in stock_columns:
                aggregations[sales_column] = "sum"

        summary_frame = stock_frame.groupby(FAMILY_COLUMN).agg(aggregations).reset_index()

        export_columns = [FAMILY_COLUMN]
        for entity in valid_entities:
            cost_column = f"{entity}.{COST_COLUMN}"
            sales_column = f"{entity}.{SALES_VALUE_LABEL}"
            margin_column = f"{MARGIN_PREFIX}{entity}"

            if sales_column in summary_frame.columns and cost_column in summary_frame.columns:
                summary_frame[margin_column] = calculate_margin(
                    summary_frame,
                    sales_column,
                    cost_column,
                )
                export_columns.extend(
                    [entity, cost_column, sales_column, margin_column]
                )
            else:
                export_columns.append(entity)

        summary_frame = summary_frame[export_columns]
        if final_titles and len(final_titles) == len(summary_frame.columns):
            summary_frame.columns = final_titles
        else:
            log.warning(
                "Title mismatch in sheet %s. Original names will be used.",
                sheet_name,
            )

        for row in dataframe_to_rows(summary_frame, index=False, header=True):
            worksheet.append(row)
        apply_excel_formatting(worksheet, is_summary=True)

    data_worksheet = workbook.create_sheet(raw_data_sheet)
    for row in dataframe_to_rows(stock_frame, index=False, header=True):
        data_worksheet.append(row)
    apply_excel_formatting(data_worksheet, is_summary=False)

    return safe_openpyxl_save(workbook, output_file, interactive=interactive)
