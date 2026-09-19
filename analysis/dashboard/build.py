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
from plotly.subplots import make_subplots
from scipy.interpolate import griddata

from analysis.env import OutputLayout
from analysis.hpc.campaign_grid import CAP_KIND, order_pressures, parse_pressure

log = logging.getLogger(__name__)

#: Conventional hues for generation carriers, shared by every figure.
CARRIER_COLOURS = {
    "Biomass": "#6b8e23",
    "Black Coal": "#1c1c1c",
    "Brown Coal": "#6b4423",
    "Gas": "#e8853a",
    "Hydro (conventional)": "#1f78b4",
    "Liquid Fuel": "#8c8c8c",
    "Solar": "#f2c511",
    "Wind": "#2f9e8f",
}

#: Carrier columns whose CSV name reads differently on the page.
CARRIER_LABELS = {"Water": "Hydro (conventional)"}

#: Fill colours for the searched-parameter grid table. A combination the campaign plan never
#: covered is left white; grey means planned but absent from the exports.
STATUS_COLOURS = {
    "solved": "#cfe8cf",
    "unaccepted": "#f2cfc9",
    "missing": "#ededed",
    "unplanned": "white",
}

#: Hatching that marks a technology mix taken from a cell that failed acceptance.
STATUS_PATTERNS = {"solved": "", "unaccepted": "/"}

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

#: Scatter-matrix dimensions: the summary measures apart from the year, which is categorical and
#: earns nothing as a row and column of its own.
MATRIX_MEASURES = [measure for measure in SUMMARY_MEASURES if measure != "year"]

#: The two per-cell acceptance tests a solve has to pass to count as solved.
ACCEPTANCE_TESTS = ["test1_serves_demand", "test4_termination"]

#: Axes the cost surface is interpolated over.
GRID_AXES = ["delivered_twh", "marginal_intensity"]

#: Fewest solved cells a year needs before its cost surface can be interpolated.
MIN_GRID_CELLS = 4

#: Vertical room each trajectory facet gets in the technology-mix figure, in pixels, and the top
#: margin the wrapped pressure titles need above the first row.
TECH_MIX_ROW_HEIGHT = 180
TECH_MIX_TOP_MARGIN = 90

#: Height of the per-year cost-surface strip, in pixels.
CONTOUR_HEIGHT = 420

#: Widths for the searched-grid table, in pixels: trajectory, year, delivered energy, then one
#: per pressure column. The figure is drawn this wide so long cell text is never squeezed.
GRID_KEY_WIDTHS = [110, 60, 110]
GRID_PRESSURE_WIDTH = 95

#: Vertical room per searched-grid row and for the table's header, in pixels. Both a header and a
#: boundary-marked cell run onto a second line, so a row gets more than a line's worth.
GRID_ROW_HEIGHT = 48
GRID_HEADER_HEIGHT = 120

#: Note placed under the technology-mix legend, which the hatching itself cannot carry. It is
#: shifted down by one legend line per carrier, so it clears the entries above it.
HATCH_NOTE = "hatched: unaccepted<br>(failed a demand or<br>termination test)"
HATCH_NOTE_LINE_HEIGHT = 24

LABELS = {
    "avg_cost": "Average cost (A$/MWh)",
    "delivered_twh": "Delivered energy (TWh)",
    "fleet_intensity": "Fleet-average intensity (t CO2e/MWh)",
    "intensity": "Emissions intensity (t CO2e/MWh)",
    "marginal_intensity": "Demand-marginal intensity (t CO2e/MWh)",
    "share": "Share of generation",
    "trajectory": "Trajectory",
    "year": "Year",
}

#: Facet row titles for the two emissions intensities the cost-family figure plots against.
MEASURE_LABELS = {
    "marginal_intensity": "Demand-marginal intensity",
    "fleet_intensity": "Fleet-average intensity",
}

#: Short measure titles, for the two figures that print every measure on one crowded set of axes.
MATRIX_LABELS = {
    **LABELS,
    "delivered_twh": "Demand (TWh)",
    "marginal_intensity": "Marginal t/MWh",
    "fleet_intensity": "Fleet t/MWh",
    "avg_cost": "Cost A$/MWh",
}


def pressure_label(key: str, separator: str = " ") -> str:
    """Spell out one pressure key the way the campaign manifest names it.

    :param key: Pressure key, e.g. ``c150`` or ``cap0005``.
    :param separator: Sits between the words of the label. ``<br>`` wraps it onto short lines, so
        a table column or a facet title stays narrow.
    :return: e.g. ``carbon price A$150/t``, ``uncapped (A$0/t)`` or
        ``cap 0.005 t CO2e/MWh by 2050``.
    """
    pressure = parse_pressure(key)
    if pressure.kind == CAP_KIND:
        return separator.join(["cap", f"{pressure.value:g}", "t CO2e/MWh", "by 2050"])
    if pressure.value == 0:
        return f"uncapped{separator}(A$0/t)"
    return f"carbon price{separator}A${pressure.value:g}/t"


def _pressure_ladder(frame: pd.DataFrame) -> list[str]:
    """The frame's pressure keys in ladder order: prices cheapest first, then caps shallow to deep."""
    return [p.key for p in order_pressures(list(frame["pressure"].unique()))]


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
    # A logarithmic axis cannot place a zero or negative intensity; such a cell is dropped.
    long = long[long["intensity"] > 0]
    figure = px.line(
        long.replace({"measure": MEASURE_LABELS}).sort_values("intensity"),
        x="intensity",
        y="avg_cost",
        color="trajectory",
        facet_col="year",
        facet_row="measure",
        category_orders={"year": sorted(frame["year"].unique())},
        custom_data=["symbol"],
        markers=True,
        log_x=True,
        labels=LABELS,
        height=750,
    )
    figure.for_each_trace(
        lambda trace: trace.update(marker_symbol=[row[0] for row in trace.customdata])
    )
    return figure.for_each_annotation(
        lambda note: note.update(text=note.text.split("=")[-1])
    )


def figure_cost_contours(frame: pd.DataFrame) -> go.Figure | None:
    """Average cost interpolated over delivered energy and marginal intensity, per year.

    Interpolation needs at least ``MIN_GRID_CELLS`` solved cells in a year, so a year with fewer
    is left out and a run with no such year gets no figure at all. Every year shares one colour
    axis, so the surfaces are directly comparable and the page carries a single colour bar. The
    intensity axes are not shared, because the reachable intensity range narrows year on year.
    """
    grid = _interpolated_cost_grid(frame)
    if grid.empty:
        return None
    years = sorted(grid["year"].unique())
    figure = make_subplots(
        1, len(years), shared_yaxes=False, subplot_titles=[str(year) for year in years]
    )
    for column, year in enumerate(years, start=1):
        figure.add_trace(_year_contour(grid[grid["year"].eq(year)]), row=1, col=column)
    figure.update_layout(
        height=CONTOUR_HEIGHT,
        coloraxis={
            "colorscale": "Viridis",
            "colorbar": {"title": {"text": LABELS["avg_cost"]}},
        },
    )
    figure.update_xaxes(title=LABELS["delivered_twh"])
    return figure.update_yaxes(title=LABELS["marginal_intensity"], col=1)


def _year_contour(block: pd.DataFrame) -> go.Contour:
    """One year's interpolated cost surface, drawn against the figure's shared colour axis."""
    surface = block.pivot_table(
        index="marginal_intensity", columns="delivered_twh", values="avg_cost"
    )
    return go.Contour(
        x=surface.columns,
        y=surface.index,
        z=surface.to_numpy(),
        coloraxis="coloraxis",
        contours={"coloring": "heatmap"},
    )


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
    """Every pair of the summary measures for the accepted cells, by trajectory and year."""
    return px.scatter_matrix(
        _accepted(frame).astype({"year": str}),
        dimensions=MATRIX_MEASURES,
        color="trajectory",
        symbol="year",
        labels=MATRIX_LABELS,
        height=1100,
    )


def figure_parallel_coordinates(frame: pd.DataFrame) -> go.Figure:
    """The same measures as parallel axes, coloured by each cell's rung on the pressure ladder.

    Colouring by the rung rather than by the pressure value keeps prices and caps on one scale,
    which their values cannot share: a price is in A$/t and a cap in t CO2e/MWh.
    """
    accepted = _accepted(frame).dropna(subset=SUMMARY_MEASURES)
    ladder = _pressure_ladder(accepted)
    rungs = {key: rung for rung, key in enumerate(ladder)}
    figure = px.parallel_coordinates(
        accepted.assign(rung=accepted["pressure"].map(rungs)),
        dimensions=[*SUMMARY_MEASURES, "total_cost"],
        color="rung",
        labels={**MATRIX_LABELS, "total_cost": "Total cost (A$/yr)"},
    )
    _tick_year_axis(figure, sorted(accepted["year"].unique()))
    return figure.update_layout(
        coloraxis_colorbar={
            "title": {"text": "Pressure"},
            "tickvals": list(rungs.values()),
            "ticktext": [pressure_label(key) for key in ladder],
        }
    )


def _tick_year_axis(figure: go.Figure, years: list[int]) -> None:
    """Tick the parallel-coordinates year axis at the milestone years, not at even steps between them."""
    axis = next(a for a in figure.data[0].dimensions if a.label == LABELS["year"])
    axis.update(tickvals=years)


def figure_search_grid(frame: pd.DataFrame) -> go.Figure:
    """Average cost for every searched cell, each cell filled by solve status.

    Delivered energy is the same across a row's pressure columns, so it gets a column of its own
    and each cell carries the cost instead. Combinations the campaign plan never covered stay
    white; grey marks a planned combination missing from the exports.
    """
    keys = ["trajectory", "year"]
    costs = (
        frame.assign(label=_cell_labels(frame))
        .pivot_table(index=keys, columns="pressure", values="label", aggfunc="first")
        .reindex(columns=_pressure_ladder(frame))
    )
    twh = frame.pivot_table(index=keys, values="delivered_twh", aggfunc="first").round(
        1
    )
    status = _grid_status(frame, costs)
    cells = twh.join(costs.fillna("")).reset_index()
    fills = [["white"]] * len(GRID_KEY_WIDTHS) + [
        [STATUS_COLOURS[label] for label in status[pressure]] for pressure in status
    ]
    return go.Figure(_grid_table(cells, fills)).update_layout(
        height=GRID_HEADER_HEIGHT + GRID_ROW_HEIGHT * len(cells),
        width=sum(GRID_KEY_WIDTHS) + GRID_PRESSURE_WIDTH * len(status.columns) + 40,
    )


def _grid_status(frame: pd.DataFrame, costs: pd.DataFrame) -> pd.DataFrame:
    """Per-cell fill key, separating a planned-but-absent combination from one never planned."""
    planned = (
        frame.groupby(["trajectory", "pressure"]).size().unstack(fill_value=0).gt(0)
    )
    covered = planned.reindex(
        index=costs.index.get_level_values("trajectory"), columns=costs.columns
    )
    status = frame.pivot_table(
        index=costs.index.names, columns="pressure", values="status", aggfunc="first"
    )
    return status.mask(status.isna() & covered.to_numpy(), "missing").fillna(
        "unplanned"
    )


def _grid_table(cells: pd.DataFrame, fills: list[list[str]]) -> go.Table:
    """Lay the searched-grid frame out as a table with fixed column widths and small text."""
    font = {"size": 12}
    return go.Table(
        columnwidth=[
            *GRID_KEY_WIDTHS,
            *([GRID_PRESSURE_WIDTH] * (len(cells.columns) - len(GRID_KEY_WIDTHS))),
        ],
        header={
            "values": [_grid_heading(name) for name in cells.columns],
            "font": font,
        },
        cells={
            "values": [cells[column] for column in cells.columns],
            "fill_color": fills,
            "font": font,
        },
    )


def _grid_heading(name: str) -> str:
    """Heading for one searched-grid column: a measure's label, or a wrapped pressure label."""
    return LABELS[name] if name in LABELS else pressure_label(name, "<br>")


def _cell_labels(frame: pd.DataFrame) -> pd.Series:
    """Average cost per cell, marked where the cell sits on the edge of the searched region."""
    cost = frame["avg_cost"].round(1).astype(str)
    return cost.where(~frame["boundary"].eq(True), cost + " (boundary)")


def figure_tech_mix(frame: pd.DataFrame) -> go.Figure:
    """Stacked generation share by carrier, one facet per trajectory and pressure.

    Cells that failed acceptance are drawn hatched rather than dropped, so a reader sees where the
    campaign has a mix it cannot stand behind instead of an unexplained gap.
    """
    long = frame.melt(
        id_vars=["trajectory", "pressure", "year", "status"],
        value_vars=list(frame.filter(regex=r"^share_")),
        var_name="carrier",
        value_name="share",
    )
    long["carrier"] = long["carrier"].str.removeprefix("share_").replace(CARRIER_LABELS)
    figure = px.bar(
        long.astype({"year": str}),
        x="year",
        y="share",
        color="carrier",
        pattern_shape="status",
        pattern_shape_map=STATUS_PATTERNS,
        facet_row="trajectory",
        facet_col="pressure",
        category_orders={"pressure": _pressure_ladder(frame)},
        color_discrete_map=CARRIER_COLOURS,
        labels=LABELS,
        height=TECH_MIX_ROW_HEIGHT * frame["trajectory"].nunique(),
    )
    figure.update_xaxes(type="category")
    figure.update_layout(legend_title_text="Carrier", margin_t=TECH_MIX_TOP_MARGIN)
    figure.for_each_trace(_carrier_legend_entry)
    figure.for_each_annotation(lambda note: note.update(text=_facet_label(note.text)))
    return figure.add_annotation(
        text=HATCH_NOTE,
        xref="paper",
        yref="paper",
        x=1.02,
        y=1,
        xanchor="left",
        yanchor="top",
        yshift=-HATCH_NOTE_LINE_HEIGHT * long["carrier"].nunique(),
        align="left",
        showarrow=False,
        font={"size": 11},
    )


def _carrier_legend_entry(trace: go.Bar) -> None:
    """Name a bar by its carrier alone, and keep its hatched twin out of the legend.

    A trace plotly express has already hidden from the legend stays hidden, so a carrier keeps its
    single entry rather than gaining one per facet.
    """
    carrier, _, status = trace.name.partition(", ")
    listed = trace.showlegend is not False and status == "solved"
    trace.update(name=carrier, showlegend=listed)


def _facet_label(text: str) -> str:
    """One facet title without its ``column=`` prefix, with a pressure key spelled out in full."""
    column, _, value = text.partition("=")
    return pressure_label(value, "<br>") if column == "pressure" else value


#: Page heading to figure builder, in the order the dashboard shows them.
SECTIONS = {
    "Cost against emissions intensity": figure_cost_families,
    "Cost surface over demand and marginal intensity": figure_cost_contours,
    "Summary measure matrix": figure_summary_matrix,
    "Parallel coordinates": figure_parallel_coordinates,
    "Searched parameter grid": figure_search_grid,
    "Technology mix": figure_tech_mix,
}


#: Each figure sits in a box the reader can drag taller or shorter by its bottom edge.
SECTION_WRAPPER = (
    '<div style="resize: vertical; overflow: auto; height: {height}px; '
    'border-bottom: 1px solid #ccc">{body}</div>'
)

#: Height for a figure that sets none of its own, in pixels.
DEFAULT_SECTION_HEIGHT = 500

#: Redraws the plot inside any section box the reader has just resized.
RESIZE_SCRIPT = (
    "<script>const fit = new ResizeObserver(entries => entries.forEach(entry =>"
    ' Plotly.Plots.resize(entry.target.querySelector(".js-plotly-plot"))));\n'
    'document.querySelectorAll("div[style*=resize]").forEach(box => fit.observe(box));</script>'
)


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
        body = figure.to_html(
            full_html=False, include_plotlyjs=index == 0, config={"responsive": True}
        )
        height = int(figure.layout.height or DEFAULT_SECTION_HEIGHT)
        sections.append(f"<h2>{heading}</h2>")
        sections.append(SECTION_WRAPPER.format(height=height + 40, body=body))
    sections.append(RESIZE_SCRIPT)
    page = layout.root / "dashboard.html"
    page.write_text("\n".join(sections), encoding="utf-8")
    if show:
        webbrowser.open(page.as_uri())
    return page
