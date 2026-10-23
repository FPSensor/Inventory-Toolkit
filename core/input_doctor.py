"""Read-only workbook compatibility inspection before running a workflow."""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from core.column_assist import ColumnAdvice, advise_columns
from core.configuration_manager import ConfigurationManager
from core.workflow_contracts import stock_input, stock_price_columns, cross_article_column
from core.setup_catalog import MODULE_LABELS, field


@dataclass(frozen=True)
class FileInspection:
    role: str
    path: str
    columns: int = 0
    sample_rows: int = 0
    checks: tuple[tuple[str, ColumnAdvice], ...] = ()
    issue: str | None = None
    headerless: bool = False

    @property
    def needs_review(self):
        return bool(self.issue or any(not advice.present for _label, advice in self.checks))


@dataclass(frozen=True)
class InputInspection:
    module: str
    files: tuple[FileInspection, ...]

    @property
    def ready(self):
        return all(not item.needs_review for item in self.files)

    def render(self):
        lines = [f"Input inspection — {MODULE_LABELS[self.module]}"]
        for item in self.files:
            lines.append(f"  {item.role}: {item.path or '(not selected)'}")
            if item.issue:
                lines.append(f"    Needs attention: {item.issue}")
                continue
            description = "headerless readings" if item.headerless else "columns"
            lines.append(f"    {item.columns} {description}; {item.sample_rows} sample rows")
            for label, advice in item.checks:
                if advice.present:
                    lines.append(f"    Found {label}: {advice.configured}")
                elif advice.suggestion:
                    lines.append(f"    Missing {label}: {advice.configured!r}; possible {advice.suggestion!r} (review before use)")
                elif advice.ambiguous:
                    lines.append(f"    Missing {label}: {advice.configured!r}; possible headers: {', '.join(advice.ambiguous)}")
                else:
                    lines.append(f"    Missing {label}: {advice.configured!r}")
        lines.append("  Input headers look compatible." if self.ready else
            "  Review missing files or headers before running. Inspection does not change the profile.")
        return "\n".join(lines)


def _requirements(config, module, *, include_sales, include_variants, grouping, has_families):
    """Capture only columns actually consumed by the selected workflow options."""
    catalog = config.get_catalog_columns()
    article = ("Article / SKU", catalog["article"], "article_hints")
    if module == "cross_check":
        settings = config.get_cross_check_config()
        return {
            "system": ("System stock", (("Article / SKU", cross_article_column(config), "article_hints"),
                ("System quantity", settings["input"]["quantity_column"], "qty_hints"))),
            "count": ("Physical count", (("Count article", settings["input"]["count_article_column"], "article_hints"), ("Count quantity", settings["input"]["count_quantity_column"], "qty_hints")) if settings["input"].get("count_mode") == "quantities" else None),
            "cost": ("Cost list", (("Cost article", settings["price_lists"]["cost"]["article_column"], "article_hints"),
                ("Cost price", settings["price_lists"]["cost"]["price_column"], "price_hints"))),
            "sales": ("Sales list", (("Sales article", settings["price_lists"]["sales"]["article_column"], "article_hints"),
                ("Sales price", settings["price_lists"]["sales"]["price_column"], "price_hints"))),
        }
    if module == "stock_processing":
        network = config.get_network_config()
        source = stock_input(config)
        stock_columns = [("Article / SKU", source["article_column"], "article_hints")]
        stock_columns.extend((f"Store {store}", source["quantity_columns"][store], None) for store in source["quantity_columns"])
        stock_columns.extend((f"Deposit for {store}", deposit, None)
            for store, deposit in source["deposit_columns"].items())
        result = {"stock": ("Raw stock", tuple(stock_columns))}
        for side, label in [("cost", "Cost list"), ("sales", "Sales list")]:
            pricing = stock_price_columns(config, side)
            result[side] = (label, tuple((f"Price {role}", name, hint) for role, name, hint in (
                ("article", pricing["article"], "article_hints"),
                ("origin", pricing["database"], "db_hints"),
                ("value", pricing["price"], "price_hints")) if name))
        return result
    if module == "yoy_reports":
        inputs = config.get_yoy_reports_config()["input"]
        required = [("Date", inputs["date_column"], "date_hints"),
            ("Units", inputs["quantity_column"], "qty_hints"),
            ("Store", inputs["branch_column"], "branch_hints"),
            ("Family" if grouping == "family" and has_families else "Article / SKU",
             inputs["grouping_column"] if grouping == "family" and has_families else inputs["item_column"],
             "family_hints" if grouping == "family" and has_families else "article_hints")]
        if include_sales:
            required.append(("Sales amount", inputs["sales_column"], "sales_hints"))
        if include_variants:
            required.append(("Variant", inputs["variant_column"], "variant_hints"))
        return {"file": ("Sales history", tuple(required))}
    raise ValueError(f"Unknown workflow: {module}")


def inspect_workflow_inputs(profile, module, files, *, include_sales=False,
                            include_variants=False, grouping="family", has_families=True):
    """Read at most five rows per input; never apply fallbacks or write config."""
    specs = _requirements(ConfigurationManager(profile), module,
        include_sales=include_sales, include_variants=include_variants,
        grouping=grouping, has_families=has_families)
    results = []
    for key, (role, required) in specs.items():
        path = str(files.get(key, "") or "").strip()
        if not path or not Path(path).is_file():
            results.append(FileInspection(role, path, issue="File is not selected or does not exist."))
            continue
        try:
            frame = pd.read_excel(path, header=None if required is None else 0, nrows=5)
            if required is None:
                results.append(FileInspection(role, path, len(frame.columns), len(frame), headerless=True,
                    issue="The scanner file is empty." if frame.empty else None))
                continue
            fields = tuple(field(str(index), label, "", hint_key=hint)
                for index, (label, _wanted, hint) in enumerate(required))
            configured = {str(index): wanted for index, (_label, wanted, _hint) in enumerate(required)}
            advice = advise_columns(fields, configured, frame.columns)
            checks = tuple((spec[0], item) for spec, item in zip(required, advice))
            results.append(FileInspection(role, path, len(frame.columns), len(frame), checks,
                issue="No data rows found." if frame.empty else None))
        except (OSError, ValueError, ImportError) as exc:
            results.append(FileInspection(role, path, issue=f"Could not read workbook: {exc}"))
    return InputInspection(module, tuple(results))
