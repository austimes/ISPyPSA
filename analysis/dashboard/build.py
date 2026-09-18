"""Turn one campaign run's export CSVs into a single self-contained ``dashboard.html``.

Four CSVs are read from ``<run>/exports/``: ``results.csv`` (one row per cell and year),
``marginals.csv`` (the cost and emissions consequence of stepping from one demand trajectory to
the next), ``manifest.csv`` and ``acceptance_per_cell.csv`` (solve status). They are joined into
one tidy frame, one row per cell-year, and every figure reads it. The source commit shown in the
page heading is read from the run's solve records, ``<run>/records/*.json``.

The page carries plotly's javascript inline, so it opens straight off the data share with no
server and no build step.
"""

from __future__ import annotations

import json
import logging
import webbrowser
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from scipy.interpolate import griddata

from analysis.env import OutputLayout

log = logging.getLogger(__name__)

#: Conventional hues for generation carriers, shared by every figure.
CARRIER_COLOURS = {
    "Biomass": "#6b8e23",
    "Black Coal": "#1c1c1c",
    "Brown Coal": "#6b4423",
    "Gas": "#e8853a",
    "Liquid Fuel": "#8c8c8c",
    "Solar": "#f2c511",
    "Water": "#1f78b4",
    "Wind": "#2f9e8f",
}

#: Fill colours for the searched-parameter grid table.
STATUS_COLOURS = {"solved": "#cfe8cf", "unaccepted": "#f2cfc9", "missing": "#ededed"}

#: Marker for each cell in the cost-family figure: filled, hollow or an open cross.
CELL_SYMBOLS = {"interior": "circle", "boundary": "circle-open", "unaccepted": "x-open"}

#: Results columns carried through unchanged, and the ones renamed for the figures.
RESULT_KEYS = [
    "cell",
    "trajectory",
    "pressure",
    "pressure_kind",
    "pressure_value",
    "year",
    "delivered_twh",
    "boundary",
]
RESULT_MEASURES = {
    "co2e_total_t_per_mwh": "fleet_intensity",
    "avg_cost_aud_per_mwh": "avg_cost",
    "total_cost_aud_per_yr": "total_cost",
}

#: Marginals columns renamed so they join the results frame on its own trajectory key.
MARGINAL_MEASURES = {
    "to_level": "trajectory",
    "marginal_co2e_t_per_mwh": "marginal_intensity",
}

#: Measures shared by the scatter matrix and the parallel-coordinates figure.
SUMMARY_MEASURES = [
    "delivered_twh",
    "marginal_intensity",
    "fleet_intensity",
    "avg_cost",
    "year",
]

#: The two per-cell acceptance tests a solve has to pass to count as solved.
ACCEPTANCE_TESTS = ["test1_serves_demand", "test4_termination"]

#: Axes the cost surface is interpolated over.
GRID_AXES = ["delivered_twh", "marginal_intensity"]

#: Fewest solved cells a year needs before its cost surface can be interpolated.
MIN_GRID_CELLS = 4

#: Vertical room each trajectory facet gets in the technology-mix figure, in pixels.
TECH_MIX_ROW_HEIGHT = 180

LABELS = {
    "avg_cost": "Average cost (A$/MWh)",
    "delivered_twh": "Delivered energy (TWh)",
    "fleet_intensity": "Fleet-average intensity (t CO2e/MWh)",
    "intensity": "Emissions intensity (t CO2e/MWh)",
    "marginal_intensity": "Demand-marginal intensity (t CO2e/MWh)",
    "share": "Share of generation",
}


def tidy_frame(exports: Path) -> pd.DataFrame:
    """Join the four export CSVs into one row per cell and milestone year.

    :param exports: The run's ``exports/`` directory.
    :return: Trajectory and pressure keys, delivered energy, both emissions intensities, cost,
        boundary flag, solve status and the per-carrier generation shares.
    """
    results = pd.read_csv(exports / "results.csv").rename(columns=RESULT_MEASURES)
    marginals = pd.read_csv(exports / "marginals.csv").rename(columns=MARGINAL_MEASURES)
    manifest = pd.read_csv(exports / "manifest.csv")[["cell", "year", "model_status"]]
    acceptance = pd.read_csv(exports / "acceptance_per_cell.csv")[
        ["cell", "year", *ACCEPTANCE_TESTS]
    ]
    shares = list(results.filter(regex=r"^share_"))
    frame = results[[*RESULT_KEYS, *RESULT_MEASURES.values(), *shares]].merge(
        marginals[["pressure", "year", "trajectory", "marginal_intensity"]],
        on=["pressure", "year", "trajectory"],
        how="left",
        validate="many_to_one",
    )
    _log_unmatched_marginals(frame)
    frame = frame.merge(manifest, on=["cell", "year"], how="left").merge(
        acceptance, on=["cell", "year"], how="left"
    )
    return frame.assign(status=_status_label(frame))


def _log_unmatched_marginals(frame: pd.DataFrame) -> None:
    """Report cell-years whose trajectory has no adjacent-trajectory step to take a marginal from."""
    unmatched = frame["marginal_intensity"].isna()
    if unmatched.any():
        trajectories = sorted(frame.loc[unmatched, "trajectory"].unique())
        log.info(
            f"Cell-years with no matching marginal: {int(unmatched.sum())}, "
            f"in trajectories {trajectories}"
        )


def _status_label(frame: pd.DataFrame) -> pd.Series:
    """Label each cell-year ``solved`` or ``unaccepted`` from its solver status and acceptance tests."""
    passed = frame[ACCEPTANCE_TESTS].eq(True).all(axis=1)
    accepted = passed & frame["model_status"].eq("Optimal")
    return pd.Series(np.where(accepted, "solved", "unaccepted"), index=frame.index)


def _accepted(frame: pd.DataFrame) -> pd.DataFrame:
    """The cell-years that solved and passed both acceptance tests."""
    return frame[frame["status"].eq("solved")]


def _cell_symbols(frame: pd.DataFrame) -> np.ndarray:
    """Pick each cell's marker: hollow on the edge of the searched region, an open cross if unaccepted."""
    edge = frame["boundary"].eq(True)
    solved = np.where(edge, CELL_SYMBOLS["boundary"], CELL_SYMBOLS["interior"])
    return np.where(frame["status"].eq("solved"), solved, CELL_SYMBOLS["unaccepted"])


def figure_cost_families(frame: pd.DataFrame) -> go.Figure:
    """Cost against emissions intensity, one line per trajectory, faceted by year.

    The top row uses the demand-marginal intensity and the bottom row the fleet average, so the
    same cost frontier can be read either way. Each point keeps its own marker, so one trace per
    trajectory carries interior, boundary and unaccepted cells alike.
    """
    long = frame.assign(symbol=_cell_symbols(frame)).melt(
        id_vars=["trajectory", "year", "pressure", "avg_cost", "symbol"],
        value_vars=["marginal_intensity", "fleet_intensity"],
        var_name="measure",
        value_name="intensity",
    )
    figure = px.line(
        long.sort_values("intensity"),
        x="intensity",
        y="avg_cost",
        color="trajectory",
        facet_col="year",
        facet_row="measure",
        custom_data=["symbol"],
        markers=True,
        labels=LABELS,
        height=750,
    )
    return figure.for_each_trace(
        lambda trace: trace.update(marker_symbol=[row[0] for row in trace.customdata])
    )


def figure_cost_contours(frame: pd.DataFrame) -> go.Figure | None:
    """Average cost interpolated over delivered energy and marginal intensity, per year.

    Interpolation needs at least ``MIN_GRID_CELLS`` solved cells in a year, so a year with fewer
    is left out and a run with no such year gets no figure at all.
    """
    grid = _interpolated_cost_grid(frame)
    if grid.empty:
        return None
    figure = px.density_contour(
        grid,
        x="delivered_twh",
        y="marginal_intensity",
        z="avg_cost",
        histfunc="avg",
        facet_col="year",
        labels=LABELS,
    )
    return figure.update_traces(contours_coloring="heatmap", colorscale="Viridis")


def _interpolated_cost_grid(frame: pd.DataFrame, size: int = 40) -> pd.DataFrame:
    """Interpolate cost onto a regular grid over ``GRID_AXES``, one block per year with enough cells."""
    solved = _accepted(frame).dropna(subset=[*GRID_AXES, "avg_cost"])
    years = solved.groupby("year")
    grids = [
        _year_grid(block, size) for _, block in years if len(block) >= MIN_GRID_CELLS
    ]
    if not grids:
        return pd.DataFrame(columns=["year", *GRID_AXES, "avg_cost"])
    return pd.concat(grids).dropna(subset=["avg_cost"])


def _year_grid(block: pd.DataFrame, size: int) -> pd.DataFrame:
    """Interpolate one year's solved cells onto a regular grid."""
    axes = [
        np.linspace(block[axis].min(), block[axis].max(), size) for axis in GRID_AXES
    ]
    demand, intensity = np.meshgrid(*axes)
    cost = griddata(
        block[GRID_AXES].to_numpy(), block["avg_cost"].to_numpy(), (demand, intensity)
    )
    return pd.DataFrame(
        {
            "year": block["year"].iloc[0],
            "delivered_twh": demand.ravel(),
            "marginal_intensity": intensity.ravel(),
            "avg_cost": cost.ravel(),
        }
    )


def figure_summary_matrix(frame: pd.DataFrame) -> go.Figure:
    """Every pair of the five summary measures for the accepted cells, coloured by trajectory."""
    return px.scatter_matrix(
        _accepted(frame),
        dimensions=SUMMARY_MEASURES,
        color="trajectory",
        symbol="pressure_kind",
        labels=LABELS,
        height=800,
    )


def figure_parallel_coordinates(frame: pd.DataFrame) -> go.Figure:
    """The same measures as parallel axes, coloured by the carbon price or cap value."""
    return px.parallel_coordinates(
        _accepted(frame).dropna(subset=SUMMARY_MEASURES),
        dimensions=[*SUMMARY_MEASURES, "total_cost"],
        color="pressure_value",
        labels=LABELS,
    )


def figure_search_grid(frame: pd.DataFrame) -> go.Figure:
    """Delivered energy for every searched cell, each cell filled by solve status."""
    keys = ["trajectory", "year"]
    cells = (
        frame.assign(label=_cell_labels(frame))
        .pivot_table(index=keys, columns="pressure", values="label", aggfunc="first")
        .fillna("")
        .reset_index()
    )
    status = frame.pivot_table(
        index=keys, columns="pressure", values="status", aggfunc="first"
    ).fillna("missing")
    fills = [["white"], ["white"]] + [
        [STATUS_COLOURS[label] for label in status[pressure]] for pressure in status
    ]
    table = go.Table(
        header={"values": list(cells.columns)},
        cells={
            "values": [cells[column] for column in cells.columns],
            "fill_color": fills,
        },
    )
    return go.Figure(table).update_layout(height=200 + 25 * len(cells))


def _cell_labels(frame: pd.DataFrame) -> pd.Series:
    """Delivered energy per cell, marked where the cell sits on the edge of the searched region."""
    twh = frame["delivered_twh"].round(1).astype(str)
    return twh.where(~frame["boundary"].eq(True), twh + " (boundary)")


def figure_tech_mix(frame: pd.DataFrame) -> go.Figure:
    """Stacked generation share by carrier, one facet per trajectory and pressure."""
    accepted = _accepted(frame)
    long = accepted.melt(
        id_vars=["trajectory", "pressure", "year"],
        value_vars=list(accepted.filter(regex=r"^share_")),
        var_name="carrier",
        value_name="share",
    )
    long["carrier"] = long["carrier"].str.removeprefix("share_")
    return px.bar(
        long,
        x="year",
        y="share",
        color="carrier",
        facet_row="trajectory",
        facet_col="pressure",
        color_discrete_map=CARRIER_COLOURS,
        labels=LABELS,
        height=TECH_MIX_ROW_HEIGHT * accepted["trajectory"].nunique(),
    )


#: Page heading to figure builder, in the order the dashboard shows them.
SECTIONS = {
    "Cost against emissions intensity": figure_cost_families,
    "Cost surface over demand and marginal intensity": figure_cost_contours,
    "Summary measure matrix": figure_summary_matrix,
    "Parallel coordinates": figure_parallel_coordinates,
    "Searched parameter grid": figure_search_grid,
    "Technology mix": figure_tech_mix,
}


def _provenance(layout: OutputLayout) -> str:
    """Name the run directory and the source commit recorded by the run's solves."""
    records = (
        json.loads(path.read_text(encoding="utf-8"))
        for path in layout.records.glob("*.json")
    )
    commits = sorted({record.get("source_git_commit") for record in records} - {None})
    return (
        f"<h1>Campaign dashboard: {layout.root.name}</h1>"
        f"<p>Run directory: {layout.root}<br>Source commit: {', '.join(commits) or 'not recorded'}</p>"
    )


def main(run: Path, show: bool = False) -> Path:
    """Write ``<run>/dashboard.html`` from the run's exports.

    :param run: A stamped run directory holding an ``exports/`` sub-directory.
    :param show: Open the finished page in the default browser.
    :return: The path written.
    """
    layout = OutputLayout(run)
    frame = tidy_frame(layout.exports)
    drawn = [(heading, build(frame)) for heading, build in SECTIONS.items()]
    sections = [_provenance(layout)]
    for index, (heading, figure) in enumerate(p for p in drawn if p[1] is not None):
        sections.append(f"<h2>{heading}</h2>")
        sections.append(figure.to_html(full_html=False, include_plotlyjs=index == 0))
    page = layout.root / "dashboard.html"
    page.write_text("\n".join(sections), encoding="utf-8")
    if show:
        webbrowser.open(page.as_uri())
    return page
