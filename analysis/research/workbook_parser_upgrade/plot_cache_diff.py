"""Diff every parsed workbook table between the v3 and v4 input packages and plot the row-count change per table.

The v3 cache was parsed with the fork's draft-derived v7.8 parser configs; the v4 cache with ``isp-workbook-parser`` 2.9.0's own
v7.8 configs. Both packages are read from ``$IO_DIR/inputs`` through ``analysis.env``. Rows are keyed by a table's first column
plus the occurrence number of that value, so a table with repeated identifiers still aligns row by row.

Run with ``uv run --with kaleido python analysis/research/workbook_parser_upgrade/plot_cache_diff.py``; writes ``table_diff.csv``,
``cache_diff.html`` and ``cache_diff.png`` beside this script.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from analysis.env import Env

_OLD_PACKAGE = "2026-09-23T19.42_isp2026_final_v3"
_NEW_PACKAGE = "2026-09-25T14.13_isp2026_final_v4"
_OUTPUT_DIR = Path(__file__).parent
_SAMPLE_KEYS = 6


def _read_table(path: Path) -> pd.DataFrame:
    """A cached table with numbers rounded to six significant figures, indexed by (first column, occurrence)."""
    table = pd.read_csv(path, low_memory=False)
    table = table.apply(
        lambda column: (
            column.map(lambda v: float(f"{v:.6g}"))
            if column.dtype.kind == "f"
            else column
        )
    )
    key = table.columns[0]
    return table.set_index(
        [table[key].astype(str), table.groupby(key, dropna=False).cumcount()]
    ).drop(columns=key)


def _changed_cells(old: pd.DataFrame, new: pd.DataFrame) -> tuple[int, float]:
    """Count of differing cells on shared rows and columns, and the largest relative change among numeric cells."""
    rows, columns = (
        old.index.intersection(new.index),
        old.columns.intersection(new.columns),
    )
    a, b = old.loc[rows, columns], new.loc[rows, columns]
    differs = ~((a == b) | (a.isna() & b.isna()))
    numeric_a, numeric_b = (
        a.apply(pd.to_numeric, errors="coerce"),
        b.apply(pd.to_numeric, errors="coerce"),
    )
    relative = ((numeric_b - numeric_a).abs() / numeric_a.abs()).where(differs)
    return int(differs.to_numpy().sum()), float(
        relative.replace(float("inf"), float("nan")).max().max()
    )


def _sample(keys: pd.Index) -> str:
    """Up to a handful of sorted row keys, for the diff table."""
    names = sorted({str(key) for key, _ in keys})
    return "; ".join(names[:_SAMPLE_KEYS]) + (
        "; ..." if len(names) > _SAMPLE_KEYS else ""
    )


def _diff_table(name: str, old_dir: Path, new_dir: Path) -> dict[str, object]:
    """One summary row comparing a table across the two caches."""
    old, new = (
        _read_table(old_dir / f"{name}.csv"),
        _read_table(new_dir / f"{name}.csv"),
    )
    added, removed = new.index.difference(old.index), old.index.difference(new.index)
    changed, max_relative = _changed_cells(old, new)
    return {
        "table": name,
        "rows_v3": len(old),
        "rows_v4": len(new),
        "columns_v3": old.shape[1] + 1,
        "columns_v4": new.shape[1] + 1,
        "rows_added": len(added),
        "rows_removed": len(removed),
        "cells_changed": changed,
        "max_relative_change": max_relative,
        "columns_added": "; ".join(sorted(new.columns.difference(old.columns))),
        "columns_removed": "; ".join(sorted(old.columns.difference(new.columns))),
        "sample_rows_added": _sample(added),
        "sample_rows_removed": _sample(removed),
    }


def build_diff() -> pd.DataFrame:
    """The per-table diff between the two caches, one row per table present in either."""
    inputs = Env.from_env().io_dir / "inputs"
    old_dir, new_dir = (
        inputs / _OLD_PACKAGE / "workbook_cache_final",
        inputs / _NEW_PACKAGE / "workbook_cache_final",
    )
    old_names, new_names = (
        {p.stem for p in old_dir.glob("*.csv")},
        {p.stem for p in new_dir.glob("*.csv")},
    )
    rows = [
        _diff_table(name, old_dir, new_dir) for name in sorted(old_names & new_names)
    ]
    rows += [
        {
            "table": name,
            "rows_v3": None,
            "rows_v4": len(pd.read_csv(new_dir / f"{name}.csv")),
        }
        for name in sorted(new_names - old_names)
    ]
    rows += [
        {
            "table": name,
            "rows_v3": len(pd.read_csv(old_dir / f"{name}.csv")),
            "rows_v4": None,
        }
        for name in sorted(old_names - new_names)
    ]
    return pd.DataFrame(rows)


def build_figure(diff: pd.DataFrame) -> go.Figure:
    """Rows added, rows removed and cells changed for every table the upgrade changed."""
    changed = diff[
        (diff["rows_added"] > 0)
        | (diff["rows_removed"] > 0)
        | (diff["cells_changed"] > 0)
    ].sort_values("table")
    figure = go.Figure()
    for column, colour in (
        ("rows_added", "#2a9d8f"),
        ("rows_removed", "#e76f51"),
        ("cells_changed", "#6c757d"),
    ):
        figure.add_bar(
            y=changed["table"],
            x=changed[column],
            name=column.replace("_", " "),
            orientation="h",
            marker_color=colour,
        )
    figure.update_layout(
        title="Parsed workbook tables changed by moving to isp-workbook-parser 2.9.0's v7.8 configs (v3 to v4 cache)",
        xaxis_title="count (log scale)",
        xaxis_type="log",
        barmode="group",
        template="plotly_white",
        width=1300,
        height=max(500, 45 * len(changed)),
        margin={"l": 520},
    )
    return figure


def main() -> None:
    """Write the diff table and the figure beside this script."""
    diff = build_diff()
    diff.to_csv(_OUTPUT_DIR / "table_diff.csv", index=False)
    figure = build_figure(diff)
    figure.write_html(_OUTPUT_DIR / "cache_diff.html", include_plotlyjs="cdn")
    figure.write_image(_OUTPUT_DIR / "cache_diff.png", scale=2)


if __name__ == "__main__":
    main()
