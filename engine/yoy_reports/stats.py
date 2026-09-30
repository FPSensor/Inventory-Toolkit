"""Concise period and group totals for completed YoY reports."""

import pandas as pd

from engine.yoy_reports.metrics import configured_branches, resolve_metric_specs


def build_yoy_stats(current_frame, previous_frame, start_date, end_date, yoy_config):
    metric_specs = resolve_metric_specs(yoy_config)
    metric = next((spec for spec in metric_specs if spec.key == "sales"), metric_specs[0])
    date_column = yoy_config["input"]["date_column"]
    branch_column = yoy_config["input"]["branch_column"]
    branches = configured_branches(yoy_config)

    current = current_frame[current_frame[branch_column].isin(branches)]
    previous = previous_frame[previous_frame[branch_column].isin(branches)]
    current_months = current.groupby(current[date_column].dt.to_period("M"))[metric.column].sum()
    previous_months = previous.groupby(previous[date_column].dt.to_period("M"))[metric.column].sum()

    def amount(value):
        return f"{value:,.0f}" if metric.key == "units" else f"{value:,.2f}"

    def comparison(current_value, previous_value):
        if previous_value == 0:
            change = "N/A (prior year is zero)"
        else:
            change = f"{(current_value - previous_value) / previous_value:+.1%}"
        return f"{amount(current_value)} vs {amount(previous_value)} ({change})"

    lines = [
        f"Period rows: {len(current_frame):,} current, {len(previous_frame):,} prior year",
        f"Monthly {metric.label.lower()} (current vs prior year, configured branches):",
    ]
    periods = pd.period_range(start_date, end_date, freq="M")
    for period in periods:
        lines.append(
            f"  {period.strftime('%b %Y')}: "
            f"{comparison(current_months.get(period, 0), previous_months.get(period - 12, 0))}"
        )

    lines.append("Group totals (selected period):")
    for group_name, members in yoy_config["groups"].items():
        group_branches = list(dict.fromkeys(members))
        if not group_branches:
            continue
        label = (
            f"{group_name.replace('_', ' ').title()} ({len(group_branches)} branches)"
            if len(group_branches) > 1 else group_branches[0]
        )
        current_total = current.loc[current[branch_column].isin(group_branches), metric.column].sum()
        previous_total = previous.loc[previous[branch_column].isin(group_branches), metric.column].sum()
        lines.append(f"  {label}: {comparison(current_total, previous_total)}")

    lines.append(
        f"Overall ({len(branches)} unique branches): "
        f"{comparison(current[metric.column].sum(), previous[metric.column].sum())}"
    )
    return lines
