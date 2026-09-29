"""Per-run Excel column selection; presentation owns the operator decision."""

from collections.abc import Callable, Mapping

import pandas as pd


def choose_input_columns(
    file_path: str,
    configured: Mapping[str, str],
    defaults: Mapping[str, str],
    confirm: Callable[[str, str, str], bool] | None = None,
) -> dict[str, str]:
    """Return actual columns by field, offering only named defaults on request.

    A missing configured column never triggers an automatic fallback. The
    caller may explicitly authorize a default for this run; no profile is edited.
    """
    columns = set(pd.read_excel(file_path, nrows=0).columns)
    resolved = {}
    for field, wanted in configured.items():
        if wanted in columns:
            resolved[field] = wanted
            continue
        default = defaults.get(field)
        if default and default != wanted and default in columns and confirm and confirm(field, wanted, default):
            resolved[field] = default
            continue
        if default and default != wanted and default not in columns and confirm and confirm(field, wanted, default):
            raise ValueError(
                f"{file_path}: configured column {wanted!r} and default {default!r} "
                f"are both absent for {field}. Available columns: {sorted(map(str, columns))}"
            )
        raise ValueError(
            f"{file_path}: configured column {wanted!r} is absent for {field}. "
            f"Default: {default!r}. Available columns: {sorted(map(str, columns))}"
        )
    return resolved
