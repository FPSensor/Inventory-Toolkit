from core.logger import log, log_debug_event
from core.system_utils import safe_openpyxl_save

try:
    from openpyxl import load_workbook
    from openpyxl.styles import Alignment, Border, Color, Font, PatternFill, Protection, Side
except ImportError:
    log.error("Missing openpyxl library for Excel formatting.")
    import sys
    sys.exit(1)

def apply_excel_formatting(output_file, interactive=True):
    log_debug_event(
        "cross_check_format_start",
        output_file=output_file,
        interactive=interactive,
    )
    wb = load_workbook(output_file)
    ws = wb.active
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
    centered = Alignment(horizontal='center', vertical='center')
    green_fill = PatternFill(start_color='C6EFCE', end_color='C6EFCE', fill_type='solid')
    red_fill = PatternFill(start_color='FFC7CE', end_color='FFC7CE', fill_type='solid')
    header_font = Font(
        name='Calibri',
        size=11,
        bold=True,
        color=Color(theme=1),
        family=2,
        scheme='minor',
    )
    header_fill = PatternFill()
    header_protection = Protection(locked=True, hidden=False)
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = ws.dimensions

    for row in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=1, max_col=ws.max_column):
        for cell in row:
            cell.border = thin_border
            cell.alignment = centered
            if cell.row == 1:
                # Pandas applies its own header style before this renderer runs.
                # Own every visible header property here so the approved output
                # does not depend on the installed Pandas/OpenPyXL versions.
                cell.font = header_font
                cell.fill = header_fill
                cell.protection = header_protection
                cell.number_format = 'General'
            if cell.row > 1 and isinstance(cell.value, (int, float)):
                col_name = ws.cell(row=1, column=cell.column).value
                if col_name in ['Diferencia', 'CTOTAL', 'VTOTAL']:
                    if cell.value < 0: cell.fill = red_fill
                    elif cell.value > 0: cell.fill = green_fill
                if col_name in ['CTOTAL', 'VTOTAL']:
                    cell.number_format = '#,##0.00'
    final_path = safe_openpyxl_save(wb, output_file, interactive=interactive)
    log_debug_event(
        "cross_check_format_saved",
        output_file=final_path,
        row_count=ws.max_row,
        column_count=ws.max_column,
    )
    return final_path
