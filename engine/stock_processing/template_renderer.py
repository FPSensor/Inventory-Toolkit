"""Fill a profile-owned Excel template, keeping its native PivotTables alive.

The template owns the design: sheets, styles, pivot layout and calculated
fields. This module replaces the data, rebuilds the pivot cache and writes the
resulting pivot values. Layouts it cannot rebuild faithfully are rejected, since
leaving them untouched would deliver the figures of the previous report.
"""

from __future__ import annotations

import math
import posixpath
from copy import deepcopy
from xml.sax.saxutils import escape, quoteattr

import pandas as pd
from lxml import etree
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.utils import get_column_letter, range_boundaries
from openpyxl.utils.cell import coordinate_from_string, column_index_from_string

from core.business_schema import UNIT_COST_PREFIX, UNIT_SALES_PREFIX
from core.logger import log, log_debug_event
from core.system_utils import safe_bytes_save
from core.workbook_package import MAIN, WorkbookPackage, parse_xml, serialize_xml, tag
from engine.stock_processing.pivot_formulas import evaluate

_DATA_MARKER = "__ITK_ROWS__"
_UNSUPPORTED_PARTS = {
    "xl/slicerCaches/": "slicers",
    "xl/timelineCaches/": "timelines",
    "xl/model/": "a data model",
    "xl/connections.xml": "external connections",
    "xl/vbaProject.bin": "macros",
}


class ReportTemplateError(ValueError):
    """Raised when a template cannot be filled without risking wrong figures."""


# Values -----------------------------------------------------------------
def _clean(value) -> str:
    return ILLEGAL_CHARACTERS_RE.sub("", str(value))


def _number(value) -> str:
    value = float(value)
    return str(int(value)) if value.is_integer() else repr(value)


def _column_values(series: pd.Series) -> tuple[bool, list]:
    """Return whether a column is numeric and its cell/cache values."""
    if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
        return True, [None if pd.isna(value) or math.isinf(value) else value for value in series]
    return False, [None if pd.isna(value) or _clean(value) == "" else _clean(value) for value in series]


def _cell(row: int, column: int, value, style, prefix="") -> str:
    attributes = f'r="{get_column_letter(column)}{row}"' + (f' s="{style}"' if style else "")
    open_tag = f"<{prefix}c {attributes}"
    if value is None:
        return f"{open_tag}/>"
    if value == "#DIV/0!":
        return f'{open_tag} t="e"><{prefix}v>#DIV/0!</{prefix}v></{prefix}c>'
    if isinstance(value, str):
        space = ' xml:space="preserve"' if value != value.strip() else ""
        return f'{open_tag} t="inlineStr"><{prefix}is><{prefix}t{space}>{escape(value)}</{prefix}t></{prefix}is></{prefix}c>'
    return f"{open_tag}><{prefix}v>{_number(value)}</{prefix}v></{prefix}c>"


# Worksheets -------------------------------------------------------------
class _Sheet:
    def __init__(self, package: WorkbookPackage, name: str, part: str):
        self.package, self.name, self.part = package, name, part
        self.root = package.xml(part)
        self.data = self.root.find(tag("sheetData"))
        self.prefix = f"{self.data.prefix}:" if self.data.prefix else ""
        self.rows = {}
        for row in self.data:
            self.rows[int(row.get("r"))] = {
                column_index_from_string(coordinate_from_string(cell.get("r"))[0]): cell
                for cell in row
            }

    def text(self, row, column, strings):
        cell = self.rows.get(row, {}).get(column)
        if cell is None:
            return None
        if cell.get("t") == "inlineStr":
            return "".join(cell.itertext())
        value = cell.find(tag("v"))
        if value is None:
            return None
        return strings[int(value.text)] if cell.get("t") == "s" else value.text

    def style(self, row, column):
        cell = self.rows.get(row, {}).get(column)
        return None if cell is None else cell.get("s")

    def require_replaceable(self, first_row, columns):
        """Refuse to discard formulas, or content outside the generated area."""
        for row, cells in self.rows.items():
            if row < first_row:
                continue
            for column, cell in cells.items():
                if cell.find(tag("f")) is not None:
                    raise ReportTemplateError(
                        f"Template sheet '{self.name}' has a formula at {cell.get('r')} inside the generated area."
                    )
                if column not in columns and len(cell):
                    raise ReportTemplateError(
                        f"Template sheet '{self.name}' has content at {cell.get('r')} next to the generated area."
                    )
        for merged in self.root.iter(tag("mergeCell")):
            if range_boundaries(merged.get("ref"))[3] >= first_row:
                raise ReportTemplateError(
                    f"Template sheet '{self.name}' has merged cells inside the generated area."
                )

    def write(self, first_row, rows, last_row, last_column):
        """Keep the rows above ``first_row`` and replace everything below."""
        for row in list(self.data):
            if int(row.get("r")) >= first_row:
                self.data.remove(row)
        self.data.append(etree.Comment(_DATA_MARKER))
        dimension = self.root.find(tag("dimension"))
        if dimension is not None:
            dimension.set("ref", f"A1:{get_column_letter(last_column)}{last_row}")
        head, tail = serialize_xml(self.root).split(f"<!--{_DATA_MARKER}-->".encode())
        self.package.parts[self.part] = head + "".join(rows).encode("utf-8") + tail

    def append_headers(self, count, names):
        """Add header cells after the template's own, in the style of the last one."""
        header = next(row for row in self.data if row.get("r") == "1")
        for cell in list(header):
            if column_index_from_string(coordinate_from_string(cell.get("r"))[0]) > count and names:
                header.remove(cell)
        for column, name in enumerate(names, count + 1):
            header.append(parse_xml(_cell(1, column, name, self.style(1, count)).replace(
                "<c ", f'<c xmlns="{MAIN}" ', 1
            ).encode("utf-8")))
        if names:
            header.attrib.pop("spans", None)

    def row(self, number, cells):
        return f'<{self.prefix}row r="{number}">{"".join(cells)}</{self.prefix}row>'


def _shared_strings(package):
    for part in package.related(package.workbook_part(), "sharedStrings"):
        return [
            "".join(node.text or "" for node in item.iter(tag("t")))
            for item in package.xml(part).findall(tag("si"))
        ]
    return []


def _replace_data_sheet(sheet: _Sheet, strings, frame: pd.DataFrame):
    """Write the data and return the template headers, their values, and the size.

    Unit prices requested for one run and absent from the template are placed to
    the right, outside the range read by its PivotTables.
    """
    if any(True for _ in sheet.root.iter(tag("tablePart"))):
        raise ReportTemplateError(f"Template data sheet '{sheet.name}' must be a plain range, not an Excel table.")
    headers = []
    while (header := sheet.text(1, len(headers) + 1, strings)) not in (None, ""):
        headers.append(header)
    if not headers:
        raise ReportTemplateError(f"Template data sheet '{sheet.name}' has no headers in row 1.")
    missing = [header for header in headers if header not in frame.columns]
    if missing:
        raise ReportTemplateError(f"Template data columns are not produced by this profile: {missing}.")
    if len(set(headers)) != len(headers):
        raise ReportTemplateError(f"Template data sheet '{sheet.name}' repeats a header.")
    if frame.empty:
        raise ReportTemplateError("There are no stock rows to place in the report template.")

    extra = [
        column for column in frame.columns
        if str(column).startswith((UNIT_COST_PREFIX, UNIT_SALES_PREFIX)) and column not in headers
    ]
    width = len(headers) + len(extra)
    sheet.require_replaceable(2, range(1, width + 1))
    if any(column > len(headers) and len(cell) for column, cell in sheet.rows[1].items()) and extra:
        raise ReportTemplateError(f"Template data sheet '{sheet.name}' has content to the right of its headers.")
    sheet.append_headers(len(headers), extra)
    columns = [_column_values(frame[header]) for header in (*headers, *extra)]
    styles = [sheet.style(2, min(index, len(headers))) for index in range(1, width + 1)]
    last_row = len(frame) + 1
    rows = [
        sheet.row(number, [
            _cell(number, index, value, style, sheet.prefix)
            for index, (value, style) in enumerate(zip(values, styles), 1)
        ])
        for number, values in enumerate(zip(*(values for _numeric, values in columns)), 2)
    ]
    last_column = get_column_letter(width)
    auto_filter = sheet.root.find(tag("autoFilter"))
    if auto_filter is not None:
        for child in list(auto_filter):
            auto_filter.remove(child)
        auto_filter.set("ref", f"A1:{last_column}{last_row}")
    for pane in sheet.root.iter(tag("pane")):
        # A saved scroll position may point past the end of a shorter report.
        frozen_rows = int(float(pane.get("ySplit", 0)))
        frozen_columns = int(float(pane.get("xSplit", 0)))
        pane.set("topLeftCell", f"{get_column_letter(frozen_columns + 1)}{frozen_rows + 1}")
    sheet.write(2, rows, last_row, width)
    return headers, dict(zip(headers, columns)), last_row, width


# Pivot caches -----------------------------------------------------------
def _caption(node):
    return node.get("v") if node.tag == tag("s") else None


def _rebuild_cache(package, part, data_sheet, headers, columns, last_row, shared_fields):
    root = package.xml(part)
    source = root.find(f"{tag('cacheSource')}/{tag('worksheetSource')}")
    if source is None or source.get("sheet") != data_sheet or not source.get("ref"):
        raise ReportTemplateError(
            f"Every template PivotTable must use a cell range of sheet '{data_sheet}' as its source."
        )
    records_parts = package.related(part, "pivotCacheRecords")
    if len(records_parts) != 1:
        raise ReportTemplateError("Template PivotTables must be saved with their source data.")
    fields = root.find(tag("cacheFields"))
    stored = [field for field in fields if field.get("databaseField") != "0"]
    if [field.get("name") for field in stored] != headers:
        raise ReportTemplateError(
            "A template PivotTable is out of date with its data sheet; refresh it in Excel and save the template."
        )
    source.set("ref", f"A1:{get_column_letter(len(headers))}{last_row}")
    root.set("recordCount", str(last_row - 1))

    encoders, old_captions, new_captions = [], {}, {}
    for index, field in enumerate(stored):
        numeric, values = columns[headers[index]]
        if field.find(tag("fieldGroup")) is not None:
            raise ReportTemplateError(f"Grouped pivot field '{headers[index]}' is not supported.")
        old = field.find(tag("sharedItems"))
        items = etree.Element(tag("sharedItems"), nsmap={None: MAIN})
        present = [value for value in values if value is not None]
        blank = len(present) != len(values)
        if index in shared_fields:
            if numeric:
                raise ReportTemplateError(f"Numeric field '{headers[index]}' cannot be a pivot row.")
            if blank:
                raise ReportTemplateError(f"Pivot row field '{headers[index]}' contains blank values.")
            captions = list(dict.fromkeys(values))
            if len({caption.casefold() for caption in captions}) != len(captions):
                raise ReportTemplateError(
                    f"Pivot row field '{headers[index]}' has values that differ only by letter case."
                )
            positions = {caption: position for position, caption in enumerate(captions)}
            old_captions[index] = [] if old is None else [_caption(node) for node in old]
            new_captions[index] = positions
            items.set("count", str(len(captions)))
            for caption in captions:
                etree.SubElement(items, tag("s")).set("v", caption)
            encoders.append([f'<x v="{positions[value]}"/>' for value in values])
        elif numeric:
            if not blank:
                items.set("containsSemiMixedTypes", "0")
            items.set("containsString", "0")
            if blank:
                items.set("containsBlank", "1")
            if present:
                items.set("containsNumber", "1")
                if all(float(value).is_integer() for value in present):
                    items.set("containsInteger", "1")
                items.set("minValue", _number(min(present)))
                items.set("maxValue", _number(max(present)))
            encoders.append(["<m/>" if value is None else f'<n v="{_number(value)}"/>' for value in values])
        else:
            if blank:
                items.set("containsBlank", "1")
            if not present:
                items.set("containsNonDate", "0")
                items.set("containsString", "0")
            if any(len(value) > 255 for value in present):
                items.set("longText", "1")
            encoders.append(["<m/>" if value is None else f"<s v={quoteattr(value)}/>" for value in values])
        if old is not None:
            field.replace(old, items)
        else:
            field.insert(0, items)
    package.parts[part] = serialize_xml(root)
    package.parts[records_parts[0]] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<pivotCacheRecords xmlns="{MAIN}" count="{last_row - 1}">'
        + "".join(f"<r>{''.join(record)}</r>" for record in zip(*encoders))
        + "</pivotCacheRecords>"
    ).encode("utf-8")
    return old_captions, new_captions


# Pivot tables -----------------------------------------------------------
def _require_supported_pivot(root, name):
    def reject(reason):
        raise ReportTemplateError(f"PivotTable '{name}' is not supported: {reason}.")

    rows = root.find(tag("rowFields"))
    if rows is None or len(rows) != 1 or int(rows[0].get("x")) < 0:
        reject("it must have exactly one row field")
    columns = root.find(tag("colFields"))
    if columns is not None and [int(field.get("x")) for field in columns] != [-2]:
        reject("column fields are not available")
    if root.find(tag("pageFields")) is not None:
        reject("report filters are not available")
    if root.find(tag("filters")) is not None:
        reject("label or value filters are not available; hide items instead")
    data = root.find(tag("dataFields"))
    if data is None or not len(data):
        reject("it has no values")
    for field in data:
        if field.get("subtotal", "sum") != "sum" or field.get("showDataAs", "normal") != "normal":
            reject(f"value '{field.get('name')}' must be a plain sum or calculated field")
    for extension in root.iter("{*}dataField"):
        if extension.tag != tag("dataField") and extension.get("pivotShowAs"):
            reject("'show values as' is not available")
    location = root.find(tag("location"))
    left, _top, right, _bottom = range_boundaries(location.get("ref"))
    if int(location.get("firstDataCol")) != 1 or right - left != len(data):
        reject("its layout must be one label column followed by the values")
    row_field = root.find(tag("pivotFields"))[int(rows[0].get("x"))]
    if row_field.find(tag("autoSortScope")) is not None:
        reject("sorting by value is not available")
    return int(rows[0].get("x")), row_field, data, location


def _rebuild_items(field, old_captions, positions, hidden):
    """Re-index pivot items by caption, keeping template captions and formats.

    ``hidden`` replaces the template visibility; ``None`` keeps it.
    """
    items = field.find(tag("items"))
    known, order, specials = {}, {}, []
    for index, item in enumerate(items):
        if item.get("t", "data") != "data":
            specials.append(item)
            continue
        caption = old_captions[int(item.get("x"))]
        known[caption], order[caption] = item, index
    ordered = sorted(positions, key=str.casefold, reverse=field.get("sortType") == "descending")
    for item in list(items):
        items.remove(item)
    for caption in ordered:
        item = deepcopy(known[caption]) if caption in known else etree.SubElement(items, tag("item"))
        item.attrib.pop("m", None)
        item.set("x", str(positions[caption]))
        if hidden is not None:
            item.attrib.pop("h", None)
            if caption in hidden:
                item.set("h", "1")
        items.append(item)
    for item in specials:
        items.append(item)
    items.set("count", str(len(items)))
    new_index = {caption: index for index, caption in enumerate(ordered)}
    return {old: new_index.get(caption) for caption, old in order.items()}, ordered


def _remap_formats(root, field_index, item_map):
    """Keep per-item formats aligned and drop those of items no longer present."""
    for reference in list(root.iter(tag("reference"))):
        if reference.get("field") != str(field_index):
            continue
        for node in reference.findall(tag("x")):
            target = item_map.get(int(node.get("v", 0)))
            if target is None:
                reference.remove(node)
            else:
                node.set("v", str(target))
        if reference.get("count", "0") == "0":
            continue
        remaining = len(reference.findall(tag("x")))
        reference.set("count", str(remaining))
        if remaining == 0:
            owner = reference
            while owner.getparent() is not None and owner.getparent().tag not in (
                tag("formats"), tag("conditionalFormats"), tag("chartFormats")
            ):
                owner = owner.getparent()
            container = owner.getparent()
            if container is None:
                raise ReportTemplateError("A pivot setting depends on an item that no longer exists.")
            container.remove(owner)
            container.set("count", str(len(container)))
            if not len(container):
                container.getparent().remove(container)


def _rebuild_pivot(package, sheet, part, frame, cache, hidden_families, family_column):
    root = package.xml(part)
    name = root.get("name")
    field_index, field, data_fields, location = _require_supported_pivot(root, name)
    cache_part, old_captions, new_captions = cache
    cache_fields = list(package.xml(cache_part).find(tag("cacheFields")))
    names = [item.get("name") for item in cache_fields]
    formulas = {item.get("name"): item.get("formula") for item in cache_fields if item.get("formula")}
    # The profile decides family visibility, so every sheet reports the same
    # totals; a template saved with other hidden families cannot contradict it.
    hidden = set(hidden_families) if names[field_index] == family_column else None

    ordered = []
    for index, positions in new_captions.items():
        target = root.find(tag("pivotFields"))[index]
        if target.find(tag("items")) is None:
            continue
        item_map, captions = _rebuild_items(
            target, old_captions[index], positions, hidden if index == field_index else None
        )
        _remap_formats(root, index, item_map)
        if index == field_index:
            ordered = captions
    items = [item for item in field.find(tag("items")) if item.get("t", "data") == "data"]
    visible = [(index, caption, items[index].get("n") or caption)
               for index, caption in enumerate(ordered) if items[index].get("h") != "1"]
    if not visible:
        raise ReportTemplateError(f"PivotTable '{name}' hides every item of '{names[field_index]}'.")

    for data_field in data_fields:
        source = names[int(data_field.get("fld"))]
        if source not in formulas and not pd.api.types.is_numeric_dtype(frame[source]):
            raise ReportTemplateError(f"PivotTable '{name}' sums the non-numeric column '{source}'.")
    numeric = [column for column in frame.columns if pd.api.types.is_numeric_dtype(frame[column])]
    keys = frame[names[field_index]].map(_clean)
    totals = frame[numeric].groupby(keys, sort=False).sum()
    grand = totals.loc[[caption for _index, caption, _label in visible]].sum()

    def measure(source, row, trail=()):
        if source not in formulas:
            if source not in row.index:
                raise ReportTemplateError(f"Calculated field uses non-numeric column '{source}'.")
            return float(row[source])
        if source in trail:
            raise ReportTemplateError(f"Calculated field '{source}' refers to itself.")
        return evaluate(formulas[source], names, lambda item: measure(item, row, (*trail, source)))

    error_text = (root.get("errorCaption") or "") if root.get("showError") == "1" else "#DIV/0!"
    old_rows = root.find(tag("rowItems"))
    has_grand = any(item.get("t") == "grand" for item in old_rows)
    left, top, right, bottom = range_boundaries(location.get("ref"))
    first = top + int(location.get("firstDataRow"))
    old_last = bottom - int(has_grand)
    sheet.require_replaceable(first, range(left, right + 1))
    for row, cells in sheet.rows.items():
        if row > bottom and any(len(cell) for cell in cells.values()):
            raise ReportTemplateError(f"Template sheet '{sheet.name}' has content below its PivotTable.")

    def line(number, label, row, style_row):
        values = [label]
        for data_field in data_fields:
            result = measure(names[int(data_field.get("fld"))], row)
            values.append((error_text or None) if result is None else result)
        return sheet.row(number, [
            _cell(number, column, value, sheet.style(style_row, column), sheet.prefix)
            for column, value in enumerate(values, left)
        ])

    last = first + len(visible) - 1
    rows = []
    for number, (_index, caption, label) in enumerate(visible, first):
        style_row = first if number == first else old_last if number == last else min(first + 1, old_last)
        rows.append(line(number, label, totals.loc[caption], style_row))
    if has_grand:
        last += 1
        label = root.get("grandTotalCaption") or sheet.text(bottom, left, _shared_strings(package)) or "Total"
        rows.append(line(last, label, grand, bottom))

    for item in list(old_rows):
        old_rows.remove(item)
    for index, _caption_text, _label in visible:
        node = etree.SubElement(etree.SubElement(old_rows, tag("i")), tag("x"))
        if index:
            node.set("v", str(index))
    if has_grand:
        grand_item = etree.SubElement(old_rows, tag("i"))
        grand_item.set("t", "grand")
        etree.SubElement(grand_item, tag("x"))
    old_rows.set("count", str(len(old_rows)))
    location.set("ref", f"{get_column_letter(left)}{top}:{get_column_letter(right)}{last}")
    package.parts[part] = serialize_xml(root)
    sheet.write(first, rows, last, max(right, 1))


# Summaries --------------------------------------------------------------
def _fill_summary(sheet, strings, summary, has_totals):
    width = len(summary.columns)
    header_width = 0
    while sheet.text(1, header_width + 1, strings) not in (None, ""):
        header_width += 1
    if header_width != width:
        raise ReportTemplateError(
            f"Template summary '{sheet.name}' has {header_width} columns; the profile generates {width}."
        )
    sheet.require_replaceable(2, range(1, width + 1))
    old_last = max(sheet.rows)
    rows = []
    for number, values in enumerate(summary.itertuples(index=False, name=None), 2):
        is_total = has_totals and number == len(summary) + 1
        style_row = old_last if is_total else 2
        rows.append(sheet.row(number, [
            _cell(number, column, None if not isinstance(value, str) and pd.isna(value) else value,
                  sheet.style(style_row, column), sheet.prefix)
            for column, value in enumerate(values, 1)
        ]))
    sheet.write(2, rows, len(summary) + 1, width)


# Entry point ------------------------------------------------------------
def fill_template(template_path, frame, summaries, raw_data_sheet, *, family_column,
                  hidden_families=(), totals_label=""):
    """Return the verified workbook bytes and warnings for unmanaged sheets.

    ``summaries`` maps sheet names to ready-to-write summary frames.
    """
    package = WorkbookPackage.read(template_path)
    for prefix, label in _UNSUPPORTED_PARTS.items():
        if any(part.startswith(prefix) for part in package.parts):
            raise ReportTemplateError(f"Report templates with {label} are not supported.")
    workbook_part = package.workbook_part()
    sheets = package.sheets()
    if raw_data_sheet not in sheets:
        raise ReportTemplateError(f"Template has no '{raw_data_sheet}' data sheet.")
    strings = _shared_strings(package)

    pivots = {}
    for name, part in sheets.items():
        found = package.related(part, "pivotTable")
        if len(found) > 1:
            raise ReportTemplateError(f"Template sheet '{name}' must contain only one PivotTable.")
        if found:
            pivots[name] = found[0]
    if raw_data_sheet in pivots:
        raise ReportTemplateError(f"Data sheet '{raw_data_sheet}' cannot contain a PivotTable.")

    cache_of, shared_fields = {}, {}
    for name, part in pivots.items():
        caches = package.related(part, "pivotCacheDefinition")
        if len(caches) != 1:
            raise ReportTemplateError(f"PivotTable on sheet '{name}' has no source cache.")
        cache_of[name] = caches[0]
        fields = package.xml(part).find(tag("pivotFields"))
        shared_fields.setdefault(caches[0], set()).update(
            index for index, field in enumerate(fields) if field.find(tag("items")) is not None
        )

    headers, columns, last_row, width = _replace_data_sheet(
        _Sheet(package, raw_data_sheet, sheets[raw_data_sheet]), strings, frame
    )
    data = frame[headers]
    rebuilt = {
        part: _rebuild_cache(package, part, raw_data_sheet, headers, columns, last_row, shared_fields.get(part, set()))
        for part in package.related(workbook_part, "pivotCacheDefinition")
    }
    for name, part in pivots.items():
        _rebuild_pivot(
            package, _Sheet(package, name, sheets[name]), part, data,
            (cache_of[name], *rebuilt[cache_of[name]]), hidden_families, family_column,
        )

    warnings = []
    for name, part in sheets.items():
        if name in pivots or name == raw_data_sheet:
            continue
        sheet = _Sheet(package, name, part)
        if name in summaries:
            _fill_summary(sheet, strings, summaries[name], bool(totals_label))
        elif any(
            cell.get("t", "n") == "n" and cell.find(tag("v")) is not None and cell.find(tag("f")) is None
            for cells in sheet.rows.values() for cell in cells.values()
        ):
            warnings.append(
                f"Template sheet '{name}' contains fixed numbers that this report does not update."
            )

    _update_workbook(package, workbook_part, raw_data_sheet, width, last_row)
    package.validate()
    return package.to_bytes(), warnings


def _update_workbook(package, part, data_sheet, width, last_row):
    root = package.xml(part)
    order = [sheet.get("name") for sheet in root.iter(tag("sheet"))]
    for defined in root.iter(tag("definedName")):
        if (
            defined.get("name") == "_xlnm._FilterDatabase"
            and defined.get("localSheetId") == str(order.index(data_sheet))
        ):
            quoted = data_sheet.replace("'", "''")
            reference = data_sheet if data_sheet.isidentifier() else f"'{quoted}'"
            defined.text = f"{reference}!$A$1:${get_column_letter(width)}${last_row}"
    calculation = root.find(tag("calcPr"))
    if calculation is not None:
        calculation.set("fullCalcOnLoad", "1")
    package.parts[part] = serialize_xml(root)


def render_stock_template(template_path, output_file, frame, summaries, raw_data_sheet, *,
                          family_column, hidden_families=(), totals_label="", on_locked=None):
    log.info("Filling report template %s...", posixpath.basename(str(template_path).replace("\\", "/")))
    payload, warnings = fill_template(
        template_path, frame, summaries, raw_data_sheet, family_column=family_column,
        hidden_families=hidden_families, totals_label=totals_label,
    )
    final_path = safe_bytes_save(payload, output_file, on_locked=on_locked)
    log_debug_event("stock_template_saved", output_file=final_path, size_bytes=len(payload))
    return final_path, warnings
