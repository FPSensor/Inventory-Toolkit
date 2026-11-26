"""Build a small report template with native PivotTables for tests."""

import posixpath

from openpyxl import Workbook

from core.files.workbook_package import MAIN, REL, WorkbookPackage

HEADERS = ["SKU", "Rubro", "Local", "Local.Costo", "Local.Venta"]
ROWS = [("A1", "Viejo", 1, 10, 20), ("A2", "Remeras", 2, 20, 50), ("A3", "Oculto", 5, 5, 5)]
CALCULATED = [("Margen", "1-(Local.Costo*2)/Local.Venta")]


def _pivot(name, values, *, hidden=(), descending=False, extra=""):
    captions = list(dict.fromkeys(row[1] for row in ROWS))
    ordered = sorted(captions, key=str.casefold, reverse=descending)
    names = HEADERS + [item[0] for item in CALCULATED]
    used = [names.index(field) for _label, field in values]
    fields = ""
    for index, _field in enumerate(names):
        data = ' dataField="1"' if index in used else ""
        if index == 1:
            items = "".join(
                '<item ' + ('h="1" ' if caption in hidden else "") + f'x="{captions.index(caption)}"/>'
                for caption in ordered
            )
            sort = ' sortType="descending"' if descending else ""
            fields += f'<pivotField axis="axisRow" showAll="0"{sort}><items count="{len(ordered) + 1}">{items}<item t="default"/></items></pivotField>'
        else:
            fields += f'<pivotField{data} showAll="0"/>'
    visible = [index for index, caption in enumerate(ordered) if caption not in hidden]
    row_items = "".join(f'<i><x v="{index}"/></i>' for index in visible) + '<i t="grand"><x/></i>'
    data_fields = "".join(
        f'<dataField name="{label}" fld="{names.index(field)}" baseField="0" baseItem="0"/>' for label, field in values
    )
    column = chr(ord("A") + len(values))
    columns = (
        f'<colFields count="1"><field x="-2"/></colFields><colItems count="{len(values)}">'
        + "".join(f'<i i="{index}"><x v="{index}"/></i>' for index in range(len(values))) + "</colItems>"
    ) if len(values) > 1 else '<colItems count="1"><i/></colItems>'
    return (
        f'<pivotTableDefinition xmlns="{MAIN}" name="{name}" cacheId="1" dataCaption="V" '
        f'grandTotalCaption="Total general"><location ref="A3:{column}{4 + len(visible)}" '
        'firstHeaderRow="0" firstDataRow="1" firstDataCol="1"/>'
        f'<pivotFields count="{len(names)}">{fields}</pivotFields><rowFields count="1"><field x="1"/></rowFields>'
        f'<rowItems count="{len(visible) + 1}">{row_items}</rowItems>{columns}'
        f'<dataFields count="{len(values)}">{data_fields}</dataFields>{extra}</pivotTableDefinition>'
    ), len(visible)


def _add(package, owner, kind, part, content, payload):
    package.parts[part] = payload.encode("utf-8")
    types = package.parts["[Content_Types].xml"].decode()
    package.parts["[Content_Types].xml"] = types.replace(
        "</Types>",
        f'<Override PartName="/{part}" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.{content}+xml"/></Types>',
    ).encode()
    _relate(package, owner, kind, part)


def _relate(package, owner, kind, part):
    folder, base = posixpath.split(owner)
    rels = f"{folder}/_rels/{base}.rels"
    current = package.parts.get(
        rels, b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>'
    ).decode()
    identifier = f"rItk{current.count('<Relationship ')}"
    package.parts[rels] = current.replace(
        "</Relationships>",
        f'<Relationship Id="{identifier}" Type="{REL}/{kind}" Target="/{part}"/></Relationships>',
    ).encode()
    return identifier


def build_template(path, *, extra="", data_sheet="Base"):
    """Two pivots on differently named sheets sharing one cache, plus a summary."""
    pivots = {
        "Resumen A": _pivot("PivotA", [("Unidades", "Local"), ("Rentab.", "Margen")], hidden=("Oculto",), extra=extra),
        "Resumen B": _pivot("PivotB", [("Importe", "Local.Venta")], descending=True),
    }
    workbook = Workbook()
    workbook.remove(workbook.active)
    for name, (_xml, visible) in pivots.items():
        sheet = workbook.create_sheet(name)
        sheet["A1"] = "Informe"
        for row in range(3, 5 + visible):
            for column in (1, 2, 3) if name == "Resumen A" else (1, 2):
                sheet.cell(row, column, "viejo")
    static = workbook.create_sheet("Fijo")
    static.append(["Rubro", "Cant", "Costo", "Venta", "Margen"])
    static.append(["Viejo", 1, 1, 1, 0.5])
    static.append(["Total", 1, 1, 1, 0.5])
    data = workbook.create_sheet(data_sheet)
    data.append(HEADERS)
    for row in ROWS:
        data.append(row)
    data.auto_filter.ref = f"A1:E{len(ROWS) + 1}"
    data.freeze_panes = "A2"
    workbook.save(path)

    package = WorkbookPackage.read(path)
    main = package.workbook_part()
    captions = list(dict.fromkeys(row[1] for row in ROWS))
    fields = ""
    for index, header in enumerate(HEADERS):
        if index == 1:
            items = "".join(f'<s v="{caption}"/>' for caption in captions)
            fields += f'<cacheField name="{header}" numFmtId="0"><sharedItems count="{len(captions)}">{items}</sharedItems></cacheField>'
        else:
            fields += f'<cacheField name="{header}" numFmtId="0"><sharedItems/></cacheField>'
    for name, formula in CALCULATED:
        fields += f'<cacheField name="{name}" numFmtId="0" formula="{formula}" databaseField="0"/>'
    definition = (
        f'<pivotCacheDefinition xmlns="{MAIN}" xmlns:r="{REL}" r:id="rItk0" recordCount="{len(ROWS)}">'
        f'<cacheSource type="worksheet"><worksheetSource ref="A1:E{len(ROWS) + 1}" sheet="{data_sheet}"/></cacheSource>'
        f'<cacheFields count="{len(HEADERS) + len(CALCULATED)}">{fields}</cacheFields></pivotCacheDefinition>'
    )
    records = "".join(
        f'<r><s v="{row[0]}"/><x v="{captions.index(row[1])}"/>' + "".join(f'<n v="{v}"/>' for v in row[2:]) + "</r>"
        for row in ROWS
    )
    cache = "xl/pivotCache/pivotCacheDefinition1.xml"
    _add(package, main, "pivotCacheDefinition", cache, "pivotCacheDefinition", definition)
    _add(package, cache, "pivotCacheRecords", "xl/pivotCache/pivotCacheRecords1.xml", "pivotCacheRecords",
         f'<pivotCacheRecords xmlns="{MAIN}" count="{len(ROWS)}">{records}</pivotCacheRecords>')
    sheets = package.sheets()
    for number, (name, (xml, _visible)) in enumerate(pivots.items(), 1):
        part = f"xl/pivotTables/pivotTable{number}.xml"
        _add(package, sheets[name], "pivotTable", part, "pivotTable", xml)
        _relate(package, part, "pivotCacheDefinition", cache)
    book = package.parts[main].decode()
    package.parts[main] = book.replace(
        "</workbook>", f'<pivotCaches><pivotCache xmlns:r="{REL}" cacheId="1" r:id="rItk{_cache_id(package, main)}"/></pivotCaches></workbook>'
    ).encode()
    path.write_bytes(package.to_bytes())
    return path


def _cache_id(package, main):
    return next(
        identifier for identifier, (kind, _part) in package.relationships(main).items()
        if kind == "pivotCacheDefinition"
    ).removeprefix("rItk")
