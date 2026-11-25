"""Read, edit and structurally verify Excel (.xlsx) packages.

OpenPyXL cannot create native PivotTables, so template reports edit the package
directly. Excel rejects mistakes that remain well-formed XML; ``validate()``
therefore runs on every generated package before it reaches the user's disk.
"""

from __future__ import annotations

import io
import posixpath
import zipfile

from lxml import etree
from openpyxl.utils import column_index_from_string, range_boundaries
from openpyxl.utils.cell import coordinate_from_string

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"


class WorkbookPackageError(ValueError):
    """Raised when a package is structurally invalid or cannot be read."""


def tag(name: str) -> str:
    return f"{{{MAIN}}}{name}"


def parse_xml(payload: bytes):
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True)
    return etree.fromstring(payload, parser)


def serialize_xml(root) -> bytes:
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


class WorkbookPackage:
    def __init__(self, parts: dict[str, bytes]):
        self.parts = parts

    @classmethod
    def read(cls, path) -> "WorkbookPackage":
        try:
            with zipfile.ZipFile(path) as archive:
                return cls({name: archive.read(name) for name in archive.namelist()})
        except zipfile.BadZipFile as exc:
            raise WorkbookPackageError(f"'{path}' is not a valid .xlsx workbook.") from exc

    def to_bytes(self) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, payload in self.parts.items():
                archive.writestr(name, payload)
        return buffer.getvalue()

    def xml(self, part: str):
        try:
            return parse_xml(self.parts[part])
        except KeyError as exc:
            raise WorkbookPackageError(f"Workbook part is missing: {part}") from exc
        except etree.XMLSyntaxError as exc:
            raise WorkbookPackageError(f"Workbook part {part} is not valid XML: {exc}") from exc

    def relationships(self, part: str) -> dict[str, tuple[str, str]]:
        """Return internal relationships as ``id -> (kind, target part)``."""
        folder, name = posixpath.split(part)
        rels = posixpath.join(folder, "_rels", f"{name}.rels")
        if rels not in self.parts:
            return {}
        result = {}
        for item in self.xml(rels).iter(f"{{{PACKAGE_REL}}}Relationship"):
            if item.get("TargetMode") == "External":
                continue
            target = item.get("Target")
            resolved = target.lstrip("/") if target.startswith("/") else posixpath.normpath(
                posixpath.join(folder, target)
            )
            result[item.get("Id")] = (item.get("Type").rsplit("/", 1)[-1], resolved)
        return result

    def related(self, part: str, kind: str) -> list[str]:
        return [target for found, target in self.relationships(part).values() if found == kind]

    def workbook_part(self) -> str:
        targets = self.related("", "officeDocument")
        if len(targets) != 1:
            raise WorkbookPackageError("Workbook has no unique main part.")
        return targets[0]

    def sheets(self) -> dict[str, str]:
        """Return worksheet names and parts in workbook order."""
        workbook = self.workbook_part()
        relations = self.relationships(workbook)
        result = {}
        for sheet in self.xml(workbook).iter(tag("sheet")):
            kind, target = relations[sheet.get(f"{{{REL}}}id")]
            if kind == "worksheet":
                result[sheet.get("name")] = target
        return result

    # Verification -------------------------------------------------------
    def validate(self) -> None:
        """Reject structures that Excel would repair or refuse to open."""
        errors: list[str] = []
        self._validate_references(errors)
        if not errors:
            sheets = self.sheets()
            styles, strings = self._style_and_string_counts()
            dimensions = {
                name: self._validate_sheet(name, part, styles, strings, errors)
                for name, part in sheets.items()
            }
            for part in self.related(self.workbook_part(), "pivotCacheDefinition"):
                self._validate_cache(part, dimensions, errors)
            for part in sheets.values():
                for pivot in self.related(part, "pivotTable"):
                    self._validate_pivot(pivot, errors)
        if errors:
            preview = "; ".join(errors[:5])
            raise WorkbookPackageError(
                f"The generated workbook is not safe to save ({len(errors)} problems): {preview}"
            )

    def _validate_references(self, errors):
        types = self.xml("[Content_Types].xml")
        declared = {item.get("PartName").lstrip("/") for item in types.iter(f"{{{CONTENT_TYPES}}}Override")}
        errors.extend(f"declared part is missing: {name}" for name in sorted(declared - set(self.parts)))
        for name in self.parts:
            if not name.endswith(".rels"):
                continue
            folder, base = posixpath.split(name)
            owner = posixpath.join(posixpath.dirname(folder), base[: -len(".rels")])
            for _kind, target in self.relationships(owner).values():
                if target not in self.parts:
                    errors.append(f"{owner or 'package'} refers to missing part {target}")

    def _style_and_string_counts(self):
        workbook = self.workbook_part()
        styles = strings = 0
        for part in self.related(workbook, "styles"):
            formats = self.xml(part).find(tag("cellXfs"))
            styles = 0 if formats is None else len(formats)
        for part in self.related(workbook, "sharedStrings"):
            strings = len(self.xml(part).findall(tag("si")))
        return styles, strings

    def _validate_sheet(self, name, part, styles, strings, errors):
        last_row = last_column = previous_row = 0
        root = self.xml(part)
        for row in root.iter(tag("row")):
            number = int(row.get("r", previous_row + 1))
            if number <= previous_row:
                errors.append(f"{name}: row {number} is out of order")
            previous_row = number
            previous_column = 0
            for cell in row.iter(tag("c")):
                reference = cell.get("r")
                if reference is None:
                    previous_column += 1
                    continue
                letters, cell_row = coordinate_from_string(reference)
                column = column_index_from_string(letters)
                if cell_row != number or column <= previous_column:
                    errors.append(f"{name}: cell {reference} is misplaced in row {number}")
                previous_column = column
                if int(cell.get("s", 0)) >= max(styles, 1):
                    errors.append(f"{name}: cell {reference} uses an unknown style")
                value = cell.find(tag("v"))
                if cell.get("t") == "s" and (value is None or int(value.text) >= strings):
                    errors.append(f"{name}: cell {reference} uses an unknown shared string")
                elif cell.get("t", "n") == "n" and value is not None:
                    try:
                        float(value.text)
                    except (TypeError, ValueError):
                        errors.append(f"{name}: cell {reference} is not a number")
            last_column = max(last_column, previous_column)
        last_row = previous_row
        auto_filter = root.find(tag("autoFilter"))
        if auto_filter is not None and range_boundaries(auto_filter.get("ref"))[3] > max(last_row, 1):
            errors.append(f"{name}: filter range exceeds the data")
        return last_row, last_column

    def _validate_cache(self, part, dimensions, errors):
        root = self.xml(part)
        source = root.find(f"{tag('cacheSource')}/{tag('worksheetSource')}")
        fields = root.find(tag("cacheFields"))
        stored = [field for field in fields if field.get("databaseField") != "0"]
        shared = [len(items) if (items := field.find(tag("sharedItems"))) is not None else 0 for field in stored]
        if source is not None and source.get("ref") and source.get("sheet") in dimensions:
            rows = range_boundaries(source.get("ref"))[3]
            if rows != dimensions[source.get("sheet")][0]:
                errors.append(f"{part}: source range does not match the data sheet")
        for records_part in self.related(part, "pivotCacheRecords"):
            records = self.xml(records_part)
            if not len(records) == int(records.get("count")) == int(root.get("recordCount", -1)):
                errors.append(f"{records_part}: record count mismatch")
            for index, record in enumerate(records):
                if len(record) != len(stored):
                    errors.append(f"{records_part}: record {index} has {len(record)} fields")
                    break
                if any(
                    item.tag == tag("x") and int(item.get("v")) >= count
                    for item, count in zip(record, shared)
                ):
                    errors.append(f"{records_part}: record {index} uses an unknown item")
                    break

    def _validate_pivot(self, part, errors):
        root = self.xml(part)
        caches = self.related(part, "pivotCacheDefinition")
        if len(caches) != 1:
            errors.append(f"{part}: pivot has no unique cache")
            return
        cache_fields = self.xml(caches[0]).find(tag("cacheFields"))
        fields = root.find(tag("pivotFields"))
        if len(fields) != len(cache_fields):
            errors.append(f"{part}: pivot and cache fields differ")
            return
        for field, cache_field in zip(fields, cache_fields):
            items = field.find(tag("items"))
            if items is None:
                continue
            shared = cache_field.find(tag("sharedItems"))
            count = 0 if shared is None else len(shared)
            if int(items.get("count")) != len(items):
                errors.append(f"{part}: item count mismatch")
            if any(int(item.get("x")) >= count for item in items if item.get("x") is not None):
                errors.append(f"{part}: pivot item outside the cache")
        row_items = root.find(tag("rowItems"))
        if row_items is not None:
            if int(row_items.get("count")) != len(row_items):
                errors.append(f"{part}: row item count mismatch")
            location = root.find(tag("location"))
            _, top, _, bottom = range_boundaries(location.get("ref"))
            if bottom - top + 1 != int(location.get("firstDataRow")) + len(row_items):
                errors.append(f"{part}: location does not match its rows")
