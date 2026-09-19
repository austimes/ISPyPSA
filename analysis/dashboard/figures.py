"""Every figure and table the campaign dashboard shows, one builder per page section.

Each builder takes the tidy cell-year frame that :func:`analysis.dashboard.build.tidy_frame`
returns and gives back either a plotly figure, ready-made html, or ``None`` where the run holds
too little to draw. Page assembly, and the order the sections appear in, live in ``build.py``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from scipy.interpolate import griddata

from analysis.hpc.campaign_grid import CAP_KIND, order_pressures, parse_pressure

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

#: Hatching that separates the two storage carriers, which share one colour scale.
STORAGE_PATTERNS = {"Battery": "", "Pumped hydro": "/"}

#: Storage carriers and duration classes as the page names them.
STORAGE_CARRIERS = {"Water": "Pumped hydro"}
DURATION_LABELS = {
    "1_under_2h": "under 2 h",
    "2_2to4h": "2 to 4 h",
    "3_4to8h": "4 to 8 h",
    "4_8h": "8 h",
    "5_over8to24h": "8 to 24 h",
    "6_over24h": "over 24 h",
}

#: Marker for each cell in the cost-frontier and cost-family figures: filled, hollow or a cross.
CELL_SYMBOLS = {"interior": "circle", "boundary": "circle-open", "unaccepted": "x-open"}

#: Viridis samples, dark to light, that colour the years in the overlaid cost-frontier figure. Four
#: are enough for the campaign's milestone years, and a longer run wraps back to the first.
YEAR_COLOURS = px.colors.sample_colorscale("Viridis", [0.0, 0.35, 0.65, 0.9])

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

#: Axes the cost surface is interpolated over.
GRID_AXES = ["delivered_twh", "marginal_intensity"]

#: Fewest solved cells a year needs before its cost surface can be interpolated.
MIN_GRID_CELLS = 4

#: The one trajectory the cost decomposition is drawn for. Every trajectory and pressure at once
#: would be fifty panels, too many to read.
CENTRAL_TRAJECTORY = "central"

#: Cost components per MWh delivered, in stacking order from the bottom up.
COST_COMPONENTS = [
    "carried capex",
    "existing-fleet FOM",
    "new build and system",
    "fuel",
    "carbon",
]

#: Unserved energy a cell has to stay under to pass acceptance, as a percentage of demand.
USE_ACCEPTANCE_PCT = 0.1

#: Vertical room each trajectory facet gets in the technology-mix and storage figures, in pixels,
#: and the top margin the wrapped pressure titles need above the first row.
TECH_MIX_ROW_HEIGHT = 180
TECH_MIX_TOP_MARGIN = 90

#: Heights of the single-strip figures, in pixels.
FRONTIER_HEIGHT = 480
#: Height of the two single-panel cost-frontier variants, which get no facet strip and so can be taller.
FRONTIER_PANEL_HEIGHT = 520
CONTOUR_HEIGHT = 420
PATHWAY_HEIGHT = 420
IMPLIED_PRICE_HEIGHT = 450
MARGINALS_HEIGHT = 620
DECOMPOSITION_HEIGHT = 520
CAP_TRACKING_HEIGHT = 700

#: Top margin a figure needs to clear the linear/log buttons drawn above it, in pixels.
SCALE_BUTTON_MARGIN = 110

#: Note placed under a patterned figure's legend, which the hatching itself cannot carry. It is
#: shifted down by one legend line per colour entry, so it clears the entries above it.
HATCH_NOTE = "hatched: unaccepted<br>(failed a demand or<br>termination test)"
STORAGE_NOTE = "hatched: pumped hydro<br>(solid: battery)"
HATCH_NOTE_LINE_HEIGHT = 24

LABELS = {
    "avg_cost": "Average cost (A$/MWh)",
    "carrier": "Carrier",
    "component": "Cost component",
    "cost_per_mwh": "Cost (A$/MWh)",
    "co2e_total_kt_per_yr": "Emissions (kt CO2e/yr)",
    "delivered_twh": "Delivered energy (TWh)",
    "duration_class": "Storage duration",
    "fleet_intensity": "Fleet-average intensity (t CO2e/MWh)",
    "implied_carbon_price_aud_per_t": "Implied carbon price (A$/t)",
    "intensity": "Emissions intensity (t CO2e/MWh)",
    "marginal_intensity": "Demand-marginal intensity (t CO2e/MWh)",
    # Short, because a facet row is only tall enough for a title of about a dozen characters.
    "power_gw": "Power (GW)",
    "pressure_name": "Pressure",
    "pressure_short": "Pressure (A$/t priced, or cap in t CO2e/MWh)",
    "pressure_value": "Cap target intensity in 2050 (t CO2e/MWh)",
    "series": "Series",
    "share": "Share of generation",
    "trajectory": "Trajectory",
    "value": "",
    "year": "Year",
}

#: Facet row titles for the two emissions intensities the cost-family figure plots against.
MEASURE_LABELS = {
    "marginal_intensity": "Demand-marginal intensity",
    "fleet_intensity": "Fleet-average intensity",
}

#: Facet row titles for the two consequences of stepping up one demand trajectory.
MARGINAL_LABELS = {
    "marginal_cost": "Demand-marginal cost (A$/MWh)",
    "marginal_intensity": "Demand-marginal intensity (t CO2e/MWh)",
}

#: Facet row titles for the two quantities a cap chain is tracked against.
TRACKING_LABELS = {
    "co2e_total_kt_per_yr": "Emissions (kt CO2e/yr)",
    "use_pct_of_demand": "Unserved energy (% of demand)",
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


def pressure_short(key: str) -> str:
    """Compact pressure label for a crowded axis, e.g. ``$150`` for a price or ``.005`` for a cap."""
    return parse_pressure(key).short


def _pressure_ladder(frame: pd.DataFrame) -> list[str]:
    """The frame's pressure keys in ladder order: prices cheapest first, then caps shallow to deep."""
    return [p.key for p in order_pressures(list(frame["pressure"].unique()))]


def _orders(frame: pd.DataFrame) -> dict[str, list]:
    """Category order for every dimension the figures facet, colour or stack by.

    Trajectories run smallest to largest load, pressures up the ladder, years in time order. Plotly
    express ignores the keys a given figure does not use, so one mapping serves them all.
    """
    ladder = _pressure_ladder(frame)
    return {
        "year": sorted(frame["year"].unique()),
        "trajectory": list(
            frame.groupby("trajectory")["delivered_twh"].max().sort_values().index
        ),
        "pressure": ladder,
        "pressure_name": [pressure_label(key) for key in ladder],
        "pressure_short": [pressure_short(key) for key in ladder],
    }


def _accepted(frame: pd.DataFrame) -> pd.DataFrame:
    """The cell-years that solved and passed both acceptance tests."""
    return frame[frame["status"].eq("solved")]


def _cell_symbols(frame: pd.DataFrame) -> np.ndarray:
    """Pick each cell's marker: hollow on the edge of the searched region, an open cross if unaccepted."""
    edge = frame["boundary"].eq(True)
    solved = np.where(edge, CELL_SYMBOLS["boundary"], CELL_SYMBOLS["interior"])
    return np.where(frame["status"].eq("solved"), solved, CELL_SYMBOLS["unaccepted"])


def _mark_cell_symbols(figure: go.Figure) -> go.Figure:
    """Give every point the marker its own ``symbol`` custom-data column names."""
    return figure.for_each_trace(
        lambda trace: trace.update(marker_symbol=[row[0] for row in trace.customdata])
    )


def _pressure_colours(frame: pd.DataFrame) -> dict[str, str]:
    """One colour per pressure, pinned to its rung on the ladder so every figure agrees.

    Left to itself plotly express hands out colours in the order it meets the pressures, which
    depends on which trajectory a figure facets first and so differs from figure to figure.
    """
    return dict(zip(_orders(frame)["pressure_name"], px.colors.qualitative.Plotly))


def _list_pressures_up_the_ladder(figure: go.Figure, frame: pd.DataFrame) -> go.Figure:
    """Relist the legend up the pressure ladder, which plotly otherwise takes from first appearance."""
    rungs = _orders(frame)["pressure_name"]
    figure.data = tuple(
        sorted(
            figure.data, key=lambda trace: rungs.index(trace.name.partition(", ")[0])
        )
    )
    return figure


def _scale_rows_apart(figure: go.Figure) -> go.Figure:
    """Give each facet row its own y scale, shared across that row's columns.

    Plotly express ties every y axis of a facet grid to one scale, which is wrong when the rows
    carry different measures. Axes sharing a vertical domain are one row, and each row follows its
    leftmost axis.
    """
    leaders: dict[tuple, str] = {}
    axes = figure.layout.to_plotly_json().items()
    for name, axis in ((n, a) for n, a in axes if n.startswith("yaxis")):
        leader = leaders.setdefault(tuple(axis["domain"]), name)
        figure.layout[name].matches = (
            None if leader == name else leader.replace("axis", "")
        )
    return figure


def _strip_facet_titles(figure: go.Figure) -> go.Figure:
    """Drop the ``column=`` prefix plotly express puts in front of every facet title."""
    return figure.for_each_annotation(
        lambda note: note.update(text=note.text.split("=")[-1])
    )


def add_axis_scale_buttons(figure: go.Figure, axes: str = "x") -> go.Figure:
    """Add a linear/log button pair above the figure, switching every one of its axes at once.

    A faceted figure has an axis per panel, so a single ``log_x`` toggle has to name them all.

    :param figure: The figure to add the buttons to, edited in place.
    :param axes: Which axes the buttons retype, ``x``, ``y`` or ``xy``.
    :return: The same figure.
    """
    prefixes = tuple(f"{axis}axis" for axis in axes)
    names = [key for key in figure.layout.to_plotly_json() if key.startswith(prefixes)]
    buttons = [
        {
            "label": scale.capitalize(),
            "method": "relayout",
            "args": [{f"{name}.type": scale for name in names}],
        }
        for scale in ("linear", "log")
    ]
    return figure.update_layout(
        margin_t=SCALE_BUTTON_MARGIN,
        updatemenus=[
            {
                "type": "buttons",
                "direction": "right",
                "buttons": buttons,
                "x": 0,
                "xanchor": "left",
                "y": 1.06,
                "yanchor": "bottom",
                "showactive": False,
            }
        ],
    )


def figure_cost_frontier(frame: pd.DataFrame) -> go.Figure:
    """Average cost against fleet-average intensity, sized by delivered energy and faceted by year.

    This is the headline view: each trajectory's pressure ladder traced from its uncapped cell out
    to its deepest cap, where cost turns up sharply for the last tonnes removed. The thin line
    joins one trajectory's cells in intensity order; the markers carry boundary and acceptance
    status as they do in the cost-family figure.
    """
    points = frame.assign(symbol=_cell_symbols(frame)).sort_values("fleet_intensity")
    orders = _orders(frame)
    figure = px.scatter(
        points,
        x="fleet_intensity",
        y="avg_cost",
        size="delivered_twh",
        size_max=18,
        color="trajectory",
        facet_col="year",
        custom_data=["symbol"],
        category_orders=orders,
        labels=LABELS,
        height=FRONTIER_HEIGHT,
    )
    _mark_cell_symbols(figure)
    ladder = px.line(
        points,
        x="fleet_intensity",
        y="avg_cost",
        color="trajectory",
        facet_col="year",
        category_orders=orders,
    )
    ladder.update_traces(line_width=1, showlegend=False, hoverinfo="skip")
    figure.add_traces(ladder.data)
    return add_axis_scale_buttons(_strip_facet_titles(figure))


def _padded_range(values: pd.Series, pad: float = 0.08) -> list[float]:
    """The span of ``values`` widened by ``pad`` of itself at each end, so markers clear the axes."""
    span = values.max() - values.min()
    return [values.min() - span * pad, values.max() + span * pad]


def _mark_animation_symbols(figure: go.Figure) -> go.Figure:
    """Give every point in every animation frame the marker its own ``symbol`` custom-data column names.

    :func:`_mark_cell_symbols` reaches the figure's own traces only, which is the first frame; the
    later frames carry their own copies and would otherwise all draw as filled circles.
    """
    _mark_cell_symbols(figure)
    for panel in figure.frames:
        for trace in panel.data:
            trace.marker.symbol = [row[0] for row in trace.customdata]
    return figure


def figure_cost_frontier_animated(frame: pd.DataFrame) -> go.Figure:
    """The cost frontier in one panel, played through the years by a slider rather than faceted.

    Same encoding as :func:`figure_cost_frontier`. Both axes are fixed to the whole run's range, so
    the frontier is seen to shift rather than the axes moving under it, and each cell keeps its
    identity across frames so its marker travels instead of jumping.
    """
    points = frame.assign(symbol=_cell_symbols(frame)).sort_values(
        ["year", "trajectory", "fleet_intensity"]
    )
    shared = {
        "x": "fleet_intensity",
        "y": "avg_cost",
        "color": "trajectory",
        "animation_frame": "year",
        "animation_group": "cell",
        "category_orders": _orders(frame),
        "range_x": _padded_range(points["fleet_intensity"]),
        "range_y": _padded_range(points["avg_cost"]),
        "labels": LABELS,
    }
    figure = px.scatter(
        points,
        size="delivered_twh",
        size_max=18,
        custom_data=["symbol"],
        height=FRONTIER_PANEL_HEIGHT,
        **shared,
    )
    _mark_animation_symbols(figure)
    ladder = px.line(points, line_group="trajectory", **shared)
    ladder.update_traces(line_width=1, showlegend=False, hoverinfo="skip")
    figure.add_traces(ladder.data)
    for panel, lines in zip(figure.frames, ladder.frames):
        panel.data = panel.data + lines.data
    return figure


def figure_cost_frontier_overlaid(frame: pd.DataFrame) -> go.Figure:
    """The cost frontier in one panel with every year drawn at once, coloured dark early to light late.

    Cost and intensity both fall year on year, so the four frontiers sit apart and the whole run's
    drift is read off one pair of axes. Here the marker shape carries the trajectory, which the
    faceted figure spends colour on; boundary and acceptance status are left to the other views.
    """
    points = frame.assign(year=frame["year"].astype(str)).sort_values("fleet_intensity")
    shared = {
        "x": "fleet_intensity",
        "y": "avg_cost",
        "color": "year",
        "color_discrete_sequence": YEAR_COLOURS,
        "category_orders": {
            **_orders(frame),
            "year": sorted(points["year"].unique()),
        },
        "labels": LABELS,
    }
    figure = px.scatter(
        points,
        size="delivered_twh",
        size_max=18,
        symbol="trajectory",
        height=FRONTIER_PANEL_HEIGHT,
        **shared,
    )
    ladder = px.line(points, line_group="trajectory", **shared)
    ladder.update_traces(line_width=1, showlegend=False, hoverinfo="skip")
    figure.add_traces(ladder.data)
    # A year-by-trajectory legend runs to twenty entries, too tall a column for the panel to show;
    # under the axis it wraps across the width instead.
    figure.update_layout(legend={"orientation": "h", "y": -0.18, "title_text": ""})
    return add_axis_scale_buttons(figure)


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
        category_orders={
            **_orders(frame),
            "measure": list(MEASURE_LABELS.values()),
        },
        custom_data=["symbol"],
        markers=True,
        log_x=True,
        labels=LABELS,
        height=750,
    )
    _mark_cell_symbols(figure)
    return add_axis_scale_buttons(_strip_facet_titles(figure))


def figure_cost_contours(frame: pd.DataFrame) -> go.Figure | None:
    """Average cost interpolated over delivered energy and marginal intensity, per year.

    Interpolation needs at least ``MIN_GRID_CELLS`` solved cells in a year, so a year with fewer
    is left out and a run with no such year gets no figure at all. Every year shares one colour
    axis, so the surfaces are directly comparable and the page carries a single colour bar. Neither
    the demand nor the intensity axis is shared, because both reachable ranges move year on year.
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
        height=CONTOUR_HEIGHT,
    )
    # Cleared bin groups let each year bin, and so scale, over its own reachable range.
    figure.update_traces(
        contours_coloring="heatmap",
        coloraxis="coloraxis",
        xbingroup=None,
        ybingroup=None,
    )
    figure.update_layout(
        coloraxis={
            "colorscale": "Viridis",
            "colorbar": {"title": {"text": LABELS["avg_cost"]}},
        }
    )
    figure.update_xaxes(matches=None, showticklabels=True)
    figure.update_yaxes(matches=None, showticklabels=True)
    return _strip_facet_titles(figure)


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


def figure_cost_pathway(frame: pd.DataFrame) -> go.Figure:
    """Average cost over the milestone years, one line per pressure and one facet per trajectory."""
    figure = px.line(
        frame.sort_values("year"),
        x="year",
        y="avg_cost",
        color="pressure_name",
        facet_col="trajectory",
        markers=True,
        category_orders=_orders(frame),
        color_discrete_map=_pressure_colours(frame),
        labels=LABELS,
        height=PATHWAY_HEIGHT,
    )
    figure.update_xaxes(tickvals=sorted(frame["year"].unique()))
    return _list_pressures_up_the_ladder(_strip_facet_titles(figure), frame)


def figure_implied_carbon_price(frame: pd.DataFrame) -> go.Figure:
    """Shadow price each cap chain's cap carries, against the 2050 target intensity it aims at.

    Only the cap chains appear: a price chain's carbon price is an input, not a solve result. Both
    axes are logarithmic because a cap two steps deeper can cost two orders of magnitude more per
    tonne.
    """
    caps = frame[frame["pressure_kind"].eq(CAP_KIND)].sort_values("pressure_value")
    figure = px.scatter(
        caps,
        x="pressure_value",
        y="implied_carbon_price_aud_per_t",
        color="trajectory",
        symbol="trajectory",
        facet_col="year",
        log_x=True,
        log_y=True,
        category_orders=_orders(frame),
        labels=LABELS,
        height=IMPLIED_PRICE_HEIGHT,
    )
    # Ticked on the caps themselves, because a log decade tick falls between two of them.
    targets = sorted(caps["pressure_value"].unique())
    figure.update_xaxes(
        tickvals=targets, ticktext=[f"{target:g}" for target in targets]
    )
    return add_axis_scale_buttons(_strip_facet_titles(figure), axes="xy")


def figure_demand_marginals(frame: pd.DataFrame) -> go.Figure:
    """Cost and emissions of stepping demand up one trajectory, over the milestone years.

    A marginal belongs to the step between two adjacent trajectories, so each column is the
    trajectory stepped up to. The lowest trajectory has nothing below it and so no marginal at all.
    """
    long = frame.dropna(subset=list(MARGINAL_LABELS)).melt(
        id_vars=["year", "pressure_name", "trajectory"],
        value_vars=list(MARGINAL_LABELS),
        var_name="measure",
        value_name="value",
    )
    steps = long.assign(stepped_to="up to " + long["trajectory"])
    figure = px.line(
        steps.replace({"measure": MARGINAL_LABELS}).sort_values("year"),
        x="year",
        y="value",
        color="pressure_name",
        symbol="trajectory",
        facet_row="measure",
        facet_col="stepped_to",
        markers=True,
        category_orders={
            **_orders(frame),
            "measure": list(MARGINAL_LABELS.values()),
            "stepped_to": [
                step
                for step in (f"up to {t}" for t in _orders(frame)["trajectory"])
                if step in set(steps["stepped_to"])
            ],
        },
        color_discrete_map=_pressure_colours(frame),
        labels=LABELS,
        height=MARGINALS_HEIGHT,
    )
    figure.update_xaxes(tickvals=sorted(frame["year"].unique()))
    figure.update_layout(legend_title_text=LABELS["pressure_name"])
    _scale_rows_apart(figure)
    _colour_legend_entries(figure)
    return _list_pressures_up_the_ladder(_strip_facet_titles(figure), frame)


def figure_cost_decomposition(frame: pd.DataFrame) -> go.Figure:
    """Average cost split into its per-MWh components, per pressure and year.

    Only the central trajectory is drawn: every trajectory at once would be fifty panels. The three
    components below fuel and carbon add up to the cost the campaign reports excluding both, so the
    full stack height is the average cost the other figures plot.
    """
    central = frame[frame["trajectory"].eq(CENTRAL_TRAJECTORY)]
    figure = px.bar(
        _cost_components(central),
        x="pressure_short",
        y="cost_per_mwh",
        color="component",
        facet_col="year",
        category_orders={**_orders(frame), "component": COST_COMPONENTS},
        labels=LABELS,
        height=DECOMPOSITION_HEIGHT,
    )
    figure.update_xaxes(type="category")
    return _strip_facet_titles(figure)


def _cost_components(frame: pd.DataFrame) -> pd.DataFrame:
    """Split each cell-year's average cost into per-MWh components, one row per component.

    Capex carried from earlier vintages and the existing fleet's fixed operating cost are annual
    totals, so both are divided by the energy delivered that year. What is left of the cost
    excluding fuel and carbon is new build and the rest of the system.
    """
    mwh = frame["delivered_twh"] * 1e6
    capex = frame["carried_capex_aud_per_yr"] / mwh
    fom = frame["existing_fleet_fom_aud_per_yr"] / mwh
    components = {
        "carried capex": capex,
        "existing-fleet FOM": fom,
        "new build and system": frame["cost_per_mwh_excl_fuel_carbon"] - capex - fom,
        "fuel": frame["diagnostic_fuel_cost_per_mwh"],
        "carbon": frame["diagnostic_carbon_cost_per_mwh"],
    }
    return frame.assign(
        pressure_short=frame["pressure"].map(pressure_short), **components
    ).melt(
        id_vars=["trajectory", "pressure_short", "year"],
        value_vars=COST_COMPONENTS,
        var_name="component",
        value_name="cost_per_mwh",
    )


def figure_cap_tracking(frame: pd.DataFrame) -> go.Figure:
    """Modelled emissions against each cap, and unserved energy against the acceptance limit.

    The dashed line in the top row is the cap the chain was solved under, so a solid line sitting
    on its dashed twin is a binding cap. The dotted line in the bottom row is the unserved-energy
    limit a cell has to stay under to be accepted.
    """
    modelled = frame.melt(
        id_vars=["trajectory", "pressure_name", "year"],
        value_vars=list(TRACKING_LABELS),
        var_name="measure",
        value_name="value",
    ).assign(series="modelled")
    caps = frame.dropna(subset=["co2_cap_annual_t"]).assign(
        measure=list(TRACKING_LABELS)[0],
        value=frame["co2_cap_annual_t"] / 1000,
        series="cap",
    )
    long = pd.concat([modelled, caps[modelled.columns]]).replace(
        {"measure": TRACKING_LABELS}
    )
    figure = px.line(
        long.sort_values("year"),
        x="year",
        y="value",
        color="pressure_name",
        line_dash="series",
        facet_row="measure",
        facet_col="trajectory",
        markers=True,
        category_orders={
            **_orders(frame),
            "measure": list(TRACKING_LABELS.values()),
            "series": ["modelled", "cap"],
        },
        color_discrete_map=_pressure_colours(frame),
        line_dash_map={"modelled": "solid", "cap": "dash"},
        labels=LABELS,
        height=CAP_TRACKING_HEIGHT,
    )
    figure.update_xaxes(tickvals=sorted(frame["year"].unique()))
    _scale_rows_apart(figure)
    _list_pressures_up_the_ladder(_strip_facet_titles(figure), frame)
    # Plotly numbers facet rows from the bottom, so row one is the unserved-energy row.
    return figure.add_hline(
        y=USE_ACCEPTANCE_PCT,
        row=1,
        line_dash="dot",
        line_width=1,
        annotation_text=f"{USE_ACCEPTANCE_PCT:g}% acceptance limit",
        annotation_font_size=10,
    )


def figure_summary_matrix(frame: pd.DataFrame) -> go.Figure:
    """Every pair of the summary measures for the accepted cells, by trajectory and year."""
    return px.scatter_matrix(
        _accepted(frame).astype({"year": str}),
        dimensions=MATRIX_MEASURES,
        color="trajectory",
        symbol="year",
        category_orders=_orders(frame),
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


#: Styling for the grid: full page width, small text, one fill per status. Each cell's span is
#: pulled out over its padding so the status fill reaches the cell's borders.
GRID_STYLE = f"""<style>
#grid {{ width: 100%; border-collapse: collapse; font-size: 12px; text-align: left }}
#grid th {{ cursor: pointer; text-align: left; border-bottom: 1px solid #bbb }}
#grid th::after {{ content: " ^" }}
#grid td {{ padding: 2px 4px; border: 1px solid #eee }}
#grid td span {{ display: block; margin: -2px -4px; padding: 2px 4px }}
{" ".join(f".{name} {{ background: {fill} }}" for name, fill in STATUS_COLOURS.items())}
</style>"""

#: Sorts the grid on the clicked heading's column, numerically where both cells read as numbers.
GRID_SORT_SCRIPT = """<script>
document.querySelectorAll("#grid th").forEach((head, column) => head.addEventListener("click", () => {
  const body = head.closest("table").querySelector("tbody"), rows = [...body.rows];
  const text = row => row.cells[column].textContent;
  const sign = head.dataset.descending ? -1 : 1;
  rows.sort((left, right) => {
    const numeric = parseFloat(text(left)) - parseFloat(text(right));
    return sign * (isNaN(numeric) ? text(left).localeCompare(text(right)) : numeric);
  });
  head.dataset.descending = head.dataset.descending ? "" : "yes";
  rows.forEach(row => body.appendChild(row));
}));
</script>"""


def html_search_grid(frame: pd.DataFrame) -> str:
    """Average cost for every searched cell as a sortable table, each cell filled by solve status.

    Delivered energy is the same across a row's pressure columns, so it gets a column of its own
    and each cell carries the cost instead. Combinations the campaign plan never covered stay
    white; grey marks a planned combination missing from the exports.

    :return: A style block, the table itself and the script that sorts it on a heading click.
    """
    keys = ["trajectory", "year"]
    costs = (
        frame.assign(label=_cell_labels(frame))
        .pivot_table(index=keys, columns="pressure", values="label", aggfunc="first")
        .reindex(columns=_pressure_ladder(frame))
    )
    status = _grid_status(frame, costs)[costs.columns]
    spans = '<span class="' + status + '">' + costs.fillna("") + "</span>"
    energy = frame.pivot_table(index=keys, values="delivered_twh", aggfunc="first")
    cells = energy.round(1).join(spans).reset_index().rename(columns=_grid_heading)
    table = cells.to_html(index=False, escape=False, classes="grid", table_id="grid")
    return GRID_STYLE + table + GRID_SORT_SCRIPT


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


def _grid_heading(name: str) -> str:
    """Heading for one searched-grid column: a measure's label, or a spelled-out pressure label."""
    return LABELS[name] if name in LABELS else pressure_label(name)


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
        category_orders=_orders(frame),
        color_discrete_map=CARRIER_COLOURS,
        labels=LABELS,
        height=TECH_MIX_ROW_HEIGHT * frame["trajectory"].nunique(),
    )
    figure.update_xaxes(type="category")
    figure.update_layout(legend_title_text="Carrier", margin_t=TECH_MIX_TOP_MARGIN)
    _colour_legend_entries(figure)
    figure.for_each_annotation(lambda note: note.update(text=_facet_label(note.text)))
    return _pattern_note(figure, HATCH_NOTE, long["carrier"].nunique())


def figure_storage_build(frame: pd.DataFrame) -> go.Figure:
    """Installed storage power by duration class, one facet per trajectory and pressure.

    Battery and pumped hydro share the duration colours and are told apart by hatching, so the
    figure reads as one storage stack rather than two.
    """
    long = _storage_rows(frame)
    figure = px.bar(
        long.astype({"year": str}),
        x="year",
        y="power_gw",
        color="duration_class",
        pattern_shape="carrier",
        pattern_shape_map=STORAGE_PATTERNS,
        facet_row="trajectory",
        facet_col="pressure",
        category_orders={
            **_orders(frame),
            "duration_class": list(DURATION_LABELS.values()),
            "carrier": list(STORAGE_PATTERNS),
        },
        labels=LABELS,
        height=TECH_MIX_ROW_HEIGHT * frame["trajectory"].nunique(),
    )
    figure.update_xaxes(type="category")
    figure.update_layout(
        legend_title_text=LABELS["duration_class"], margin_t=TECH_MIX_TOP_MARGIN
    )
    _colour_legend_entries(figure)
    figure.for_each_annotation(lambda note: note.update(text=_facet_label(note.text)))
    return _pattern_note(figure, STORAGE_NOTE, long["duration_class"].nunique())


def _storage_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """Melt the per-carrier, per-duration storage power columns back into one row each."""
    long = frame.melt(
        id_vars=["trajectory", "pressure", "year"],
        value_vars=list(frame.filter(regex=r"^storage_")),
        var_name="key",
        value_name="power_gw",
    ).dropna(subset=["power_gw"])
    # e.g. "storage_Battery_2_2to4h" names the carrier and then the duration class.
    names = long["key"].str.removeprefix("storage_").str.split("_", n=1, expand=True)
    return long.assign(
        carrier=names[0].replace(STORAGE_CARRIERS),
        duration_class=names[1].replace(DURATION_LABELS),
    )


def _colour_legend_entries(figure: go.Figure) -> go.Figure:
    """Name each trace by its colour alone, and list every colour exactly once.

    Plotly express names a trace that carries a second encoding ``<colour>, <pattern>`` and lists
    each combination, which runs to dozens of entries. Listing the first trace of each colour
    instead keeps one entry per colour, whichever pattern that first trace happens to wear.
    """
    listed: set[str] = set()

    def entry(trace: go.Trace) -> None:
        colour = trace.name.partition(", ")[0]
        first = trace.showlegend is not False and colour not in listed
        trace.update(name=colour, showlegend=first)
        listed.update({colour} if first else set())

    return figure.for_each_trace(entry)


def _pattern_note(figure: go.Figure, text: str, entries: int) -> go.Figure:
    """Note under a patterned figure's legend saying what the hatched bars are."""
    return figure.add_annotation(
        text=text,
        xref="paper",
        yref="paper",
        x=1.02,
        y=1,
        xanchor="left",
        yanchor="top",
        yshift=-HATCH_NOTE_LINE_HEIGHT * entries,
        align="left",
        showarrow=False,
        font={"size": 11},
    )


def _facet_label(text: str) -> str:
    """One facet title without its ``column=`` prefix, with a pressure key spelled out in full."""
    column, _, value = text.partition("=")
    return pressure_label(value, "<br>") if column == "pressure" else value
