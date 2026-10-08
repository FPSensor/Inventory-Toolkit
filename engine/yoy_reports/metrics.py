"""Metric contracts for Year-over-Year reports."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from core.workflow_errors import WorkflowError, ErrorCode


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
            raise WorkflowError(ErrorCode.CONFIG_REQUIRED_FIELD,
                f"YoY metric '{metric_key}' requires a configured input column.",
                module="yoy_reports", step="yoy_period", field=f"input.{template['input_key']}"
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
        raise WorkflowError(ErrorCode.CONFIG_REQUIRED_FIELD,
            "YoY Reports requires at least one non-empty report group before a workbook can be generated.",
            module="yoy_reports", step="yoy_groups", field="groups"
        )
    return branches


def select_run_metrics(yoy_config: dict, include_sales_amounts: bool = False) -> dict:
    """Select unit counts and optional revenue for an interactive run only."""
    selected = deepcopy(yoy_config)
    selected["output"]["metrics"] = ["units", "sales"] if include_sales_amounts else ["units"]
    resolve_metric_specs(selected)
    return selected
