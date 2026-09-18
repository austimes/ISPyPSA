"""Turn one campaign run's export CSVs into a single self-contained ``dashboard.html``.

Everything is read from ``<run>/exports/``: ``results.csv`` (one row per cell and year),
``marginals.csv`` (the cost and emissions consequence of stepping from one demand
trajectory to the next), ``manifest.csv`` and ``acceptance_per_cell.csv`` (solve status).
The four are joined into one tidy frame, one row per cell-year, and every figure reads it.

The page carries plotly's javascript inline, so it opens straight off the data share with
no server and no build step.
"""

from __future__ import annotations

import json
import webbrowser
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from scipy.interpolate import griddata

from analysis.env import OutputLayout

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
    "Battery": "#7b52ab",
}

#: Fill colours for the searched-parameter grid table.
STATUS_COLOURS = {"Optimal": "#cfe8cf", "boundary": "#f7dcae", "missing": "#ededed"}

#: Cells on the edge of the searched region are drawn hollow.
BOUNDARY_SYMBOLS = {"interior": "circle", "boundary": "circle-open"}

#: Results columns carried through unchanged, and the ones renamed for the figures.
RESULT_KEYS = "cell trajectory pressure pressure_kind pressure_value year delivered_twh boundary".split()
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
SUMMARY_MEASURES = (
    "delivered_twh marginal_intensity fleet_intensity avg_cost year".split()
)

#: The two per-cell acceptance tests a solve has to pass to count as solved.
ACCEPTANCE_TESTS = ["test1_serves_demand", "test4_termination"]

#: Axes the cost surface is interpolated over.
GRID_AXES = ["delivered_twh", "marginal_intensity"]

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
    :return: Trajectory and pressure keys, delivered energy, both emissions intensities,
        cost, boundary flag, solve status and the per-carrier generation shares.
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
    )
    frame = frame.merge(manifest, on=["cell", "year"], how="left").merge(
        acceptance, on=["cell", "year"], how="left"
    )
    return frame.assign(status=_status_label(frame))


def _status_label(frame: pd.DataFrame) -> pd.Series:
    """Label each cell-year ``Optimal``, ``boundary`` or ``missing`` for the grid table."""
    accepted = frame[ACCEPTANCE_TESTS].eq(True).all(axis=1)
    solved = frame["model_status"].eq("Optimal") & accepted
    labels = pd.Series("missing", index=frame.index).where(~solved, "Optimal")
    return labels.where(~frame["boundary"].eq(True), "boundary")


def figure_cost_families(frame: pd.DataFrame) -> go.Figure:
    """Cost against emissions intensity, one line per trajectory, faceted by year.

    The top row uses the demand-marginal intensity and the bottom row the fleet average,
    so the same cost frontier can be read either way.
    """
    long = frame.melt(
        id_vars=["trajectory", "year", "pressure", "avg_cost", "boundary"],
        value_vars=["marginal_intensity", "fleet_intensity"],
        var_name="measure",
        value_name="intensity",
    )
    long["boundary"] = np.where(long["boundary"], "boundary", "interior")
    return px.line(
        long.sort_values("intensity"),
        x="intensity",
        y="avg_cost",
        color="trajectory",
        symbol="boundary",
        symbol_map=BOUNDARY_SYMBOLS,
        facet_col="year",
        facet_row="measure",
        markers=True,
        labels=LABELS,
        height=750,
    )


def figure_cost_contours(frame: pd.DataFrame) -> go.Figure:
    """Average cost interpolated over delivered energy and marginal intensity, per year."""
    figure = px.density_contour(
        _interpolated_cost_grid(frame),
        x="delivered_twh",
        y="marginal_intensity",
        z="avg_cost",
        histfunc="avg",
        facet_col="year",
        labels=LABELS,
    )
    return figure.update_traces(contours_coloring="heatmap", colorscale="Viridis")


def _interpolated_cost_grid(frame: pd.DataFrame, size: int = 40) -> pd.DataFrame:
    """Interpolate cost onto a regular grid over ``GRID_AXES``, one block per year."""
    solved = frame.dropna(subset=[*GRID_AXES, "avg_cost"])
    grids = [_year_grid(block, size) for _, block in solved.groupby("year")]
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
    """Every pair of the five summary measures, coloured by trajectory."""
    return px.scatter_matrix(
        frame,
        dimensions=SUMMARY_MEASURES,
        color="trajectory",
        symbol="pressure_kind",
        labels=LABELS,
        height=800,
    )


def figure_parallel_coordinates(frame: pd.DataFrame) -> go.Figure:
    """The same measures as parallel axes, coloured by the carbon price or cap value."""
    return px.parallel_coordinates(
        frame.dropna(subset=SUMMARY_MEASURES),
        dimensions=[*SUMMARY_MEASURES, "total_cost"],
        color="pressure_value",
        labels=LABELS,
    )


def figure_search_grid(frame: pd.DataFrame) -> go.Figure:
    """Delivered energy for every searched cell, each cell filled by solve status."""
    keys = ["trajectory", "year"]
    cells = (
        frame.pivot_table(index=keys, columns="pressure", values="delivered_twh")
        .round(1)
        .reset_index()
    )
    status = frame.pivot_table(
        index=keys, columns="pressure", values="status", aggfunc="first"
    )
    fills = [["white"], ["white"]] + [
        [STATUS_COLOURS.get(label, "#ededed") for label in status[p]] for p in status
    ]
    table = go.Table(
        header={"values": list(cells.columns)},
        cells={
            "values": [cells[column] for column in cells.columns],
            "fill_color": fills,
        },
    )
    return go.Figure(table).update_layout(height=200 + 25 * len(cells))


def figure_tech_mix(frame: pd.DataFrame) -> go.Figure:
    """Stacked generation share by carrier, one facet per trajectory and pressure."""
    long = frame.melt(
        id_vars=["trajectory", "pressure", "year"],
        value_vars=list(frame.filter(regex=r"^share_")),
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
        height=1500,
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
    sections = [_provenance(layout)]
    for index, (heading, build_figure) in enumerate(SECTIONS.items()):
        sections.append(f"<h2>{heading}</h2>")
        sections.append(
            build_figure(frame).to_html(full_html=False, include_plotlyjs=index == 0)
        )
    page = layout.root / "dashboard.html"
    page.write_text("\n".join(sections), encoding="utf-8")
    if show:
        webbrowser.open(page.as_uri())
    return page
