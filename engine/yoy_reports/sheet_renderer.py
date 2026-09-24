"""Worksheet-level rendering for Year-over-Year sales reports."""

import pandas as pd
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from core.business_schema import SIZE_COLUMN


def apply_style(cell, is_header=False, is_total=False, num_format=None, indent=0):
    cell.alignment = Alignment(
        horizontal="center" if indent == 0 else "left",
        vertical="center",
        indent=indent,
    )
    cell.border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )
    if is_header:
        cell.font = Font(bold=True)
        cell.fill = PatternFill(
            start_color="D3D3D3",
            end_color="D3D3D3",
            fill_type="solid",
        )
    if is_total:
        cell.font = Font(bold=True)
        cell.fill = PatternFill(
            start_color="F0F0F0",
            end_color="F0F0F0",
            fill_type="solid",
        )
    if num_format:
        cell.number_format = num_format


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
    main_block_width = len(all_branches) + 2

    worksheet.merge_cells(
        start_row=1,
        start_column=1,
        end_row=1,
        end_column=main_block_width,
    )
    title_cell = worksheet["A1"]
    if pd.isna(start_date) or pd.isna(end_date):
        title_cell.value = "Sales (No Data)"
    else:
        title_cell.value = (
            f'Sales from {start_date.strftime("%B %d, %Y")} '
            f'to {end_date.strftime("%B %d, %Y")}'
        )
    apply_style(title_cell, is_header=True)

    main_headers = [grouping_column] + all_branches + ["Totals"]
    for column_index, header in enumerate(main_headers, 1):
        apply_style(
            worksheet.cell(row=2, column=column_index, value=header),
            is_header=True,
        )

    current_row = 3
    main_start_row = current_row

    if include_sizes and size_column in current_frame.columns:
        worksheet.sheet_properties.outlinePr.summaryBelow = False
        clean_current_frame = current_frame.copy()
        clean_current_frame[size_column] = (
            clean_current_frame[size_column].fillna("-").astype(str)
        )

        pivot = pd.pivot_table(
            clean_current_frame,
            values=quantity_column,
            index=[grouping_column, size_column],
            columns=branch_column,
            aggfunc="sum",
            fill_value=0,
        )
        for branch in all_branches:
            if branch not in pivot.columns:
                pivot[branch] = 0
        pivot = pivot[all_branches]
        families = pivot.index.get_level_values(0).unique().sort_values()

        for family in families:
            family_data = pivot.loc[family]
            family_start_row = current_row
            apply_style(
                worksheet.cell(row=current_row, column=1, value=family),
                is_header=False,
            )
            worksheet.cell(row=current_row, column=1).font = Font(bold=True)
            current_row += 1

            for size_value, row in family_data.iterrows():
                # "Talle" is part of the current workbook contract, not an
                # internal identifier; formulas below intentionally match it.
                apply_style(
                    worksheet.cell(
                        row=current_row,
                        column=1,
                        value=f"  Talle: {size_value}",
                    ),
                    indent=1,
                )
                for index, branch in enumerate(all_branches):
                    value = row[branch]
                    apply_style(
                        worksheet.cell(
                            row=current_row,
                            column=2 + index,
                            value=value if value != 0 else None,
                        ),
                        num_format="#,##0",
                    )

                branch_letters = [
                    get_column_letter(2 + index)
                    for index in range(len(all_branches))
                ]
                apply_style(
                    worksheet.cell(
                        row=current_row,
                        column=main_block_width,
                        value="="
                        + "+".join(
                            f"{column_letter}{current_row}"
                            for column_letter in branch_letters
                        ),
                    ),
                    num_format="#,##0",
                )

                worksheet.row_dimensions[current_row].outlineLevel = 1
                worksheet.row_dimensions[current_row].hidden = True
                current_row += 1

            family_end_row = current_row - 1
            for index in range(len(all_branches) + 1):
                column_letter = get_column_letter(2 + index)
                apply_style(
                    worksheet.cell(
                        row=family_start_row,
                        column=2 + index,
                        value=(
                            f"=SUM(${column_letter}{family_start_row + 1}:"
                            f"${column_letter}{family_end_row})"
                        ),
                    ),
                    is_total=True,
                    num_format="#,##0",
                )
    else:
        current_pivot = pd.pivot_table(
            current_frame,
            values=quantity_column,
            index=grouping_column,
            columns=branch_column,
            aggfunc="sum",
            fill_value=0,
        )
        for branch in all_branches:
            if branch not in current_pivot.columns:
                current_pivot[branch] = 0
        current_pivot = current_pivot[all_branches].sort_index()

        for item, row in current_pivot.iterrows():
            apply_style(worksheet.cell(row=current_row, column=1, value=item))
            for index, branch in enumerate(all_branches):
                value = row[branch]
                apply_style(
                    worksheet.cell(
                        row=current_row,
                        column=2 + index,
                        value=value if value != 0 else None,
                    ),
                    num_format="#,##0",
                )

            branch_letters = [
                get_column_letter(2 + index)
                for index in range(len(all_branches))
            ]
            apply_style(
                worksheet.cell(
                    row=current_row,
                    column=main_block_width,
                    value="="
                    + "+".join(
                        f"{column_letter}{current_row}"
                        for column_letter in branch_letters
                    ),
                ),
                num_format="#,##0",
                is_total=True,
            )
            current_row += 1

    main_end_row = current_row - 1
    if main_end_row < main_start_row:
        main_end_row = main_start_row

    apply_style(
        worksheet.cell(row=current_row, column=1, value="Totals"),
        is_total=True,
    )
    for index in range(len(all_branches) + 1):
        column_letter = get_column_letter(2 + index)
        if include_sizes and size_column in current_frame.columns:
            formula = (
                f'=SUMIF($A${main_start_row}:$A${main_end_row}, "<>  Talle*", '
                f'${column_letter}${main_start_row}:${column_letter}${main_end_row})'
            )
        else:
            formula = (
                f"=SUM(${column_letter}${main_start_row}:"
                f"${column_letter}${main_end_row})"
            )
        apply_style(
            worksheet.cell(row=current_row, column=2 + index, value=formula),
            is_total=True,
            num_format="#,##0",
        )

    current_row += 3

    for group_name, branches in groups.items():
        if not branches:
            continue

        # A Global block only exists when a group contains multiple branches.
        has_global = len(branches) > 1
        block_count = len(branches) + (1 if has_global else 0)
        group_width = 1 + block_count * 3

        worksheet.merge_cells(
            start_row=current_row,
            start_column=1,
            end_row=current_row,
            end_column=group_width,
        )
        apply_style(
            worksheet.cell(
                row=current_row,
                column=1,
                value=f'YoY Comparison - {group_name.replace("_", " ").title()}',
            ),
            is_header=True,
        )
        current_row += 1

        column_index = 2
        for branch in branches:
            worksheet.merge_cells(
                start_row=current_row,
                start_column=column_index,
                end_row=current_row,
                end_column=column_index + 1,
            )
            apply_style(
                worksheet.cell(row=current_row, column=column_index, value=branch),
                is_header=True,
            )
            apply_style(
                worksheet.cell(row=current_row, column=column_index + 1),
                is_header=True,
            )
            apply_style(
                worksheet.cell(row=current_row, column=column_index + 2),
                is_header=True,
            )
            column_index += 3

        if has_global:
            worksheet.merge_cells(
                start_row=current_row,
                start_column=column_index,
                end_row=current_row,
                end_column=column_index + 1,
            )
            apply_style(
                worksheet.cell(row=current_row, column=column_index, value="Global"),
                is_header=True,
            )
            apply_style(
                worksheet.cell(row=current_row, column=column_index + 1),
                is_header=True,
            )
            apply_style(
                worksheet.cell(row=current_row, column=column_index + 2),
                is_header=True,
            )

        current_row += 1

        apply_style(
            worksheet.cell(row=current_row, column=1, value=grouping_column),
            is_header=True,
        )
        column_index = 2
        previous_year = previous_start.year
        current_year = end_date.year if pd.notna(end_date) else start_date.year + 1

        for _branch in branches:
            apply_style(
                worksheet.cell(
                    row=current_row,
                    column=column_index,
                    value=previous_year,
                ),
                is_header=True,
            )
            apply_style(
                worksheet.cell(
                    row=current_row,
                    column=column_index + 1,
                    value=current_year,
                ),
                is_header=True,
            )
            apply_style(
                worksheet.cell(row=current_row, column=column_index + 2, value="%"),
                is_header=True,
            )
            column_index += 3

        if has_global:
            apply_style(
                worksheet.cell(
                    row=current_row,
                    column=column_index,
                    value=previous_year,
                ),
                is_header=True,
            )
            apply_style(
                worksheet.cell(
                    row=current_row,
                    column=column_index + 1,
                    value=current_year,
                ),
                is_header=True,
            )
            apply_style(
                worksheet.cell(row=current_row, column=column_index + 2, value="%"),
                is_header=True,
            )

        previous_pivot = pd.pivot_table(
            previous_frame[previous_frame[branch_column].isin(branches)],
            values=quantity_column,
            index=grouping_column,
            columns=branch_column,
            aggfunc="sum",
            fill_value=0,
        )
        current_pivot = pd.pivot_table(
            current_frame[current_frame[branch_column].isin(branches)],
            values=quantity_column,
            index=grouping_column,
            columns=branch_column,
            aggfunc="sum",
            fill_value=0,
        )

        all_items = list(
            dict.fromkeys(list(previous_pivot.index) + list(current_pivot.index))
        )
        all_items.sort()

        for branch in branches:
            if branch not in previous_pivot.columns:
                previous_pivot[branch] = 0
            if branch not in current_pivot.columns:
                current_pivot[branch] = 0

        previous_pivot = previous_pivot.reindex(all_items, fill_value=0)
        current_pivot = current_pivot.reindex(all_items, fill_value=0)

        current_row += 1
        group_start_row = current_row
        for item in all_items:
            apply_style(worksheet.cell(row=current_row, column=1, value=item))
            column_index = 2
            previous_cells = []
            current_cells = []

            for branch in branches:
                previous_value = previous_pivot.loc[item, branch]
                current_value = current_pivot.loc[item, branch]
                apply_style(
                    worksheet.cell(
                        row=current_row,
                        column=column_index,
                        value=previous_value if previous_value != 0 else None,
                    ),
                    num_format="#,##0",
                )
                apply_style(
                    worksheet.cell(
                        row=current_row,
                        column=column_index + 1,
                        value=current_value if current_value != 0 else None,
                    ),
                    num_format="#,##0",
                )

                previous_letter = get_column_letter(column_index)
                current_letter = get_column_letter(column_index + 1)
                previous_cells.append(f"{previous_letter}{current_row}")
                current_cells.append(f"{current_letter}{current_row}")

                apply_style(
                    worksheet.cell(
                        row=current_row,
                        column=column_index + 2,
                        value=(
                            f'=IF({previous_letter}{current_row}=0, "N/A", '
                            f'({current_letter}{current_row}-{previous_letter}{current_row})/'
                            f'{previous_letter}{current_row})'
                        ),
                    ),
                    num_format="0.00%",
                )
                column_index += 3

            if has_global:
                global_previous_letter = get_column_letter(column_index)
                global_current_letter = get_column_letter(column_index + 1)
                apply_style(
                    worksheet.cell(
                        row=current_row,
                        column=column_index,
                        value="=" + "+".join(previous_cells),
                    ),
                    num_format="#,##0",
                )
                apply_style(
                    worksheet.cell(
                        row=current_row,
                        column=column_index + 1,
                        value="=" + "+".join(current_cells),
                    ),
                    num_format="#,##0",
                )
                apply_style(
                    worksheet.cell(
                        row=current_row,
                        column=column_index + 2,
                        value=(
                            f'=IF({global_previous_letter}{current_row}=0, "N/A", '
                            f'({global_current_letter}{current_row}-{global_previous_letter}{current_row})/'
                            f'{global_previous_letter}{current_row})'
                        ),
                    ),
                    num_format="0.00%",
                )

            current_row += 1

        group_end_row = current_row - 1
        if group_end_row < group_start_row:
            group_end_row = group_start_row

        apply_style(
            worksheet.cell(row=current_row, column=1, value="Totals"),
            is_total=True,
        )
        column_index = 2
        for _branch in branches:
            previous_letter = get_column_letter(column_index)
            current_letter = get_column_letter(column_index + 1)
            apply_style(
                worksheet.cell(
                    row=current_row,
                    column=column_index,
                    value=(
                        f"=SUM(${previous_letter}{group_start_row}:"
                        f"${previous_letter}{group_end_row})"
                    ),
                ),
                is_total=True,
                num_format="#,##0",
            )
            apply_style(
                worksheet.cell(
                    row=current_row,
                    column=column_index + 1,
                    value=(
                        f"=SUM(${current_letter}{group_start_row}:"
                        f"${current_letter}{group_end_row})"
                    ),
                ),
                is_total=True,
                num_format="#,##0",
            )
            apply_style(
                worksheet.cell(
                    row=current_row,
                    column=column_index + 2,
                    value=(
                        f'=IF({previous_letter}{current_row}=0, "N/A", '
                        f'({current_letter}{current_row}-{previous_letter}{current_row})/'
                        f'{previous_letter}{current_row})'
                    ),
                ),
                is_total=True,
                num_format="0.00%",
            )
            column_index += 3

        if has_global:
            global_previous_letter = get_column_letter(column_index)
            global_current_letter = get_column_letter(column_index + 1)
            apply_style(
                worksheet.cell(
                    row=current_row,
                    column=column_index,
                    value=(
                        f"=SUM(${global_previous_letter}{group_start_row}:"
                        f"${global_previous_letter}{group_end_row})"
                    ),
                ),
                is_total=True,
                num_format="#,##0",
            )
            apply_style(
                worksheet.cell(
                    row=current_row,
                    column=column_index + 1,
                    value=(
                        f"=SUM(${global_current_letter}{group_start_row}:"
                        f"${global_current_letter}{group_end_row})"
                    ),
                ),
                is_total=True,
                num_format="#,##0",
            )
            apply_style(
                worksheet.cell(
                    row=current_row,
                    column=column_index + 2,
                    value=(
                        f'=IF({global_previous_letter}{current_row}=0, "N/A", '
                        f'({global_current_letter}{current_row}-{global_previous_letter}{current_row})/'
                        f'{global_previous_letter}{current_row})'
                    ),
                ),
                is_total=True,
                num_format="0.00%",
            )

        current_row += 3

    for column_index in range(1, worksheet.max_column + 1):
        worksheet.column_dimensions[get_column_letter(column_index)].width = 15
    worksheet.column_dimensions["A"].width = 30
