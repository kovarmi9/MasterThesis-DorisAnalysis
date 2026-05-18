from __future__ import annotations

from typing import Literal

import pandas as pd

__all__ = [
    "deduplicate_orbit_epochs",
]


ResolutionStrategy = Literal["first", "last", "mean"]
DEFAULT_VALUE_COLUMNS = ("x", "y", "z", "vx", "vy", "vz")


def _infer_key_columns(df: pd.DataFrame) -> tuple[str, ...]:
    time_column = df.attrs.get("time_column")
    if not time_column:
        raise ValueError("DataFrame attrs must contain 'time_column'.")

    key_columns = [time_column]
    if "satellite" in df.columns:
        key_columns.append("satellite")

    missing = [column for column in key_columns if column not in df.columns]
    if missing:
        raise ValueError(f"Missing key columns in dataframe: {missing}")

    return tuple(key_columns)


def _infer_value_columns(df: pd.DataFrame) -> tuple[str, ...]:
    return tuple(column for column in DEFAULT_VALUE_COLUMNS if column in df.columns)


def _resolve_group(
    group: pd.DataFrame,
    *,
    keep: ResolutionStrategy,
    value_columns: tuple[str, ...],
) -> pd.Series:
    if keep == "first":
        return group.iloc[0].copy()

    if keep == "last":
        return group.iloc[-1].copy()

    if keep != "mean":
        raise ValueError(f"Unsupported keep strategy: {keep!r}")

    resolved = group.iloc[0].copy()
    for column in value_columns:
        resolved[column] = group[column].mean(skipna=True)
    return resolved


def deduplicate_orbit_epochs(
    df: pd.DataFrame,
    *,
    keep: ResolutionStrategy = "mean",
    compute_statistics: bool = True,
) -> pd.DataFrame:
    """
    Deduplicate orbit epochs and return a dataframe with deduplication metadata.

    Duplicate keys are defined by the dataframe time column declared in
    ``df.attrs["time_column"]`` and, if present, also by the ``satellite`` column.

    Metadata are stored in ``df.attrs["deduplication"]`` as:
    - ``strategy``: selected overlap resolution strategy
    - ``overlap_count``: number of duplicate keys / overlaps
    - ``column_std``: mean standard deviation within duplicate groups for state columns

    Parameters
    ----------
    compute_statistics : bool
        If True, compute per-column standard deviation across overlaps and store it
        in metadata. If False, perform deduplication without those statistics.
    """
    if df.empty:
        result = df.copy()
        result.attrs.update(df.attrs)
        result.attrs["deduplication"] = {
            "strategy": keep,
            "overlap_count": 0,
            "column_std": {},
        }
        return result

    key_columns = _infer_key_columns(df)
    value_columns = _infer_value_columns(df)
    working_df = df.copy()

    resolved_rows: list[pd.Series] = []
    overlap_count = 0
    raw_group_stds: dict[str, list[float]] = {column: [] for column in value_columns} if compute_statistics else {}

    grouped = working_df.groupby(list(key_columns), sort=False, dropna=False)

    for _, group in grouped:
        group = group.copy()
        resolved_rows.append(_resolve_group(group, keep=keep, value_columns=value_columns))

        if len(group) <= 1:
            continue

        overlap_count += 1

        if compute_statistics:
            for column in value_columns:
                numeric_values = pd.to_numeric(group[column], errors="coerce").dropna()
                if len(numeric_values) >= 2:
                    raw_group_stds[column].append(float(numeric_values.std(ddof=0)))

    deduplicated_df = pd.DataFrame(resolved_rows)
    sort_columns = [column for column in key_columns if column in deduplicated_df.columns]
    if sort_columns:
        deduplicated_df = deduplicated_df.sort_values(by=sort_columns).reset_index(drop=True)
    else:
        deduplicated_df = deduplicated_df.reset_index(drop=True)

    deduplicated_df.attrs.update(df.attrs)
    deduplicated_df.attrs["deduplication"] = {
        "strategy": keep,
        "overlap_count": overlap_count,
        "column_std": {
            column: (float(pd.Series(stds).mean()) if stds else None)
            for column, stds in raw_group_stds.items()
        } if compute_statistics else {},
    }

    return deduplicated_df
