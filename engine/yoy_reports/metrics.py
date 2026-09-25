"""Metric contracts for Year-over-Year reports."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricSpec:
    """Resolved workbook behavior for one configured YoY metric."""

    key: str
    label: str
    column: str
    number_format: str


_METRIC_TEMPLATES = {
    "units": {
        "label": "Units Sold",
        "input_key": "quantity_column",
        "number_format": "#,##0",
    },
    "sales": {
        "label": "Sales Amount",
        "input_key": "sales_column",
        "number_format": "#,##0.00",
    },
}


def resolve_metric_specs(yoy_config: dict) -> list[MetricSpec]:
    """Resolve configured metric names into concrete input columns/rendering rules."""
    input_config = yoy_config["input"]
    configured = yoy_config["output"].get("metrics", ["units"])
    if not configured:
        raise ValueError("YoY Reports requires at least one enabled output metric.")

    resolved = []
    seen = set()
    for metric_key in configured:
        if metric_key in seen:
            continue
        seen.add(metric_key)
        try:
            template = _METRIC_TEMPLATES[metric_key]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported YoY metric '{metric_key}'. Supported metrics: "
                f"{', '.join(_METRIC_TEMPLATES)}."
            ) from exc

        column = str(input_config.get(template["input_key"], "")).strip()
        if not column:
            raise ValueError(
                f"YoY metric '{metric_key}' requires input.{template['input_key']} to be configured."
            )
        resolved.append(
            MetricSpec(
                key=metric_key,
                label=template["label"],
                column=column,
                number_format=template["number_format"],
            )
        )
    return resolved


def configured_branches(yoy_config: dict) -> list[str]:
    """Return unique configured branches, rejecting an unusable empty group plan."""
    groups = yoy_config.get("groups", {})
    branches = list(
        dict.fromkeys(
            branch
            for group_branches in groups.values()
            for branch in group_branches
            if str(branch).strip()
        )
    )
    if not branches:
        raise ValueError(
            "YoY Reports requires at least one non-empty report group before a workbook can be generated."
        )
    return branches
