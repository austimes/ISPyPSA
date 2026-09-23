"""Every figure and table the campaign dashboard shows, one builder per page section.

Each builder takes the tidy cell-year frame that :func:`analysis.dashboard.build.tidy_frame`
returns and gives back either a plotly figure, ready-made html, or ``None`` where the run holds
too little to draw. Page assembly, and the order the sections appear in, live in ``build.py``.
"""

from __future__ import annotations

from itertools import cycle, product

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from analysis.env import PACKAGE_ROOT, REPO_ROOT
from analysis.hpc.campaign_grid import (
    BASE_CHAIN_KEY,
    CAP_KIND,
    order_pressures,
    parse_pressure,
    split_chain_id,
)

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
    "Battery": "#9467bd",
    "Pumped hydro": "#7fb8dd",
}

#: Carrier columns whose CSV name reads differently on the page.
CARRIER_LABELS = {"Water": "Hydro (conventional)"}

#: The technology mix's last stack segment, and its colour: demand no generation served. It is not a
#: carrier, so it sits outside ``CARRIER_COLOURS`` and after every carrier in the stack.
UNSERVED_CARRIER = "Unserved"
UNSERVED_COLOUR = "#d62728"

#: Hatching that marks a technology mix taken from a cell that failed acceptance.
STATUS_PATTERNS = {"solved": "", "unaccepted": "/"}

#: Hatching for the technology mix stack: a cell's acceptance status, overridden by a dotted fill on
#: the storage discharge segments whatever the status.
MIX_PATTERNS = {**STATUS_PATTERNS, "storage": "."}

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

#: The three pathway-intensity panels in page order, each titled and with the unit its y axis carries.
#: Emissions are in Mt CO2e/TWh and fuel inputs in PJ/TWh, which are the ShARP units and numerically
#: the t CO2e/MWh and GJ/MWh the campaign exports.
INTENSITY_PANELS = [
    ("Conversion cost intensity", "A$/MWh"),
    ("Emissions intensity", "Mt CO2e/TWh"),
    ("Input intensity", "PJ/TWh"),
]

#: Derived AEMO draft ISP scenario emissions intensity, committed beside the research topic that derives it, and how the
#: emissions panel draws it: one legend group, one grey dotted line per scenario and a shaded range behind them.
AEMO_INTENSITY_CSV = (
    PACKAGE_ROOT
    / "research"
    / "aemo_scenario_intensity"
    / "aemo_scenario_intensity.csv"
)
AEMO_SCENARIOS = ["Slower Growth", "Step Change", "Accelerated Transition"]
AEMO_LEGEND_GROUP = "AEMO draft ISP"
AEMO_LINE_COLOUR = "#808080"
AEMO_BAND_FILL = "rgba(120,120,120,0.18)"

#: ShARP's current-policy grid supply and its clean ladder converted to intensity, committed beside the research topic that
#: derives it, and how every figure draws it: one dashed neutral line per panel or year under one legend entry.
SHARP_REFERENCE_CSV = (
    PACKAGE_ROOT / "research" / "sharp_grid_reference" / "sharp_grid_reference.csv"
)
SHARP_NAME = "ShARP current policy (approx.)"
SHARP_LINE = {"color": "#404040", "dash": "dash", "width": 1.5}
SHARP_BAND_NAME = "ShARP clean ladder reach (approx.)"
SHARP_BAND_FILL = "rgba(64,64,64,0.08)"
#: ShARP's planned columns the pathway-intensity panels draw, in ``INTENSITY_PANELS`` order.
SHARP_PATHWAY_COLUMNS = [
    "planned_cost_aud_per_mwh",
    "planned_t_co2e_per_mwh",
    "planned_pj_per_twh",
]
MWH_PER_TWH = 1e6

#: Fuel input columns the input-intensity panel draws, each named and dashed as it draws them.
FUEL_INPUTS = {
    "gj_per_mwh_coal": ("Coal", "solid"),
    "gj_per_mwh_natural_gas": ("Gas", "dash"),
    "gj_per_mwh_biomass": ("Biomass", "dot"),
}

#: Milestone spacing of the campaign's chains. An increment cell is a single-year solve seeded from
#: its base chain's state one step back, so its fan is drawn from the base point at that year.
BRANCH_STEP = 5

#: Hues for the increment-grid fans, lighter than the chain palette so the base chains read over them.
INCREMENT_FAN_COLOURS = px.colors.qualitative.Light24

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

#: Cost-input categories of ``input_costs.csv``, in panel order, titled with the unit each is
#: priced in. A category the run's inputs do not cover gets no panel.
INPUT_COST_LABELS = {
    "build_cost": "New-entrant build cost (A$/MW)",
    "fuel_price": "Fuel price (A$/GJ)",
    "fuel_adder": "Supply-curve tranche adder (A$/GJ)",
}


#: Hues for the cost inputs that are not generation carriers. The default ten-colour sequence
#: repeats itself several times over a run's technologies, fuels and tranches, which puts two lines
#: of one panel in the same colour; this one is long enough not to.
INPUT_COST_COLOURS = px.colors.qualitative.Dark24

#: Heights of the single-strip figures, in pixels.
#: Tall enough for the chain legend, which runs to one entry per trajectory and pressure combination.
INTENSITIES_HEIGHT = 820
MARGINALS_HEIGHT = 620
DECOMPOSITION_HEIGHT = 520
#: Tall enough for the cost-input legend, which runs to one entry per technology, fuel and tranche.
INPUT_COSTS_HEIGHT = 760

#: Top margin a figure needs to clear the linear/log buttons drawn above it, in pixels.
SCALE_BUTTON_MARGIN = 110

#: Note placed under a patterned figure's legend, which the hatching itself cannot carry. It is
#: shifted down by one legend line per colour entry, so it clears the entries above it.
HATCH_NOTE = (
    "hatched: unaccepted<br>(failed a demand or<br>termination test)<br><br>"
    "dotted: storage discharge,<br>which re-delivers charged<br>"
    "energy, so the stack exceeds<br>demand by the energy<br>discharged"
)
STORAGE_NOTE = "hatched: pumped hydro<br>(solid: battery)"
HATCH_NOTE_LINE_HEIGHT = 24

LABELS = {
    "avg_cost": "Average cost (A$/MWh)",
    "carrier": "Carrier",
    "cell_label": "Cell: the base chain and each increment cell",
    "component": "Cost component",
    "cost_per_mwh": "Cost (A$/MWh)",
    "co2e_total_kt_per_yr": "Emissions (kt CO2e/yr)",
    "delivered_twh": "Delivered energy (TWh)",
    "demand_level": "Demand level (multiple of the base cell's)",
    "intensity_level": "Intensity level (multiple of the base cell's cap)",
    "duration_class": "Storage duration",
    "fleet_intensity": "Fleet-average intensity (t CO2e/MWh)",
    "implied_carbon_price_aud_per_t": "Implied carbon price (A$/t)",
    "intensity": "Emissions intensity (t CO2e/MWh)",
    "link": "Transmission link",
    "marginal_intensity": "Demand-marginal intensity (t CO2e/MWh)",
    "p_nom_opt_mw": "Link capacity, existing plus expansion (MW)",
    # Short, because a facet row is only tall enough for a title of about a dozen characters.
    "power_gw": "Power (GW)",
    "pressure_name": "Pressure",
    "pressure_short": "Pressure (A$/t priced, or cap in t CO2e/MWh)",
    "pressure_value": "Cap target intensity in 2050 (t CO2e/MWh)",
    "premium_aud_m_per_yr": "Premium paid (A$m/yr)",
    "curve": "Cost curve",
    "delta_cost_aud_m_per_yr": "Delta cost (A$m/yr)",
    "cumulative_mw": "Cumulative capacity (MW)",
    "adder": "Cost step (A$/MW/yr)",
    "group": "Curve group and period",
    "gw": "Capacity (GW)",
    "segment": "Fleet segment",
    "series": "Series",
    "trajectory": "Demand trajectory",
    "twh": "Energy delivered (TWh)",
    "value": "",
    "year": "Year",
}

#: Facet row titles for the two consequences of stepping up one demand trajectory.
MARGINAL_LABELS = {
    "marginal_cost": "Demand-marginal cost (A$/MWh)",
    "marginal_intensity": "Demand-marginal intensity (t CO2e/MWh)",
}


def pressure_label(key: str) -> str:
    """Spell out one pressure key the way the campaign manifest names it.

    :param key: Pressure key, e.g. ``c150`` or ``cap0005``.
    :return: e.g. ``carbon price A$150/t``, ``uncapped (A$0/t)``,
        ``cap 0.005 t CO2e/MWh by 2050`` or ``Step Change intensity path``.
    """
    if key == BASE_CHAIN_KEY:
        return "Step Change intensity path"
    pressure = parse_pressure(key)
    if pressure.kind == CAP_KIND:
        return f"cap {pressure.value:g} t CO2e/MWh by 2050"
    if pressure.value == 0:
        return "uncapped (A$0/t)"
    return f"carbon price A${pressure.value:g}/t"


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
    """Replace plotly express's ``column=value`` facet titles with the value alone, except that a
    trajectory facet says what it is: ``demand central``."""
    return figure.for_each_annotation(
        lambda note: note.update(text=_facet_text(note.text))
    )


def _facet_text(text: str) -> str:
    """Facet title for one ``column=value`` annotation."""
    column, _, value = text.partition("=")
    return f"demand {value}" if column == "trajectory" else value


def _axis_names(figure: go.Figure, axes: str) -> list[str]:
    """Every axis the figure's layout holds for the named letters, e.g. ``xaxis``, ``xaxis2``.

    A faceted figure has an axis per panel, so a button that retypes or ties axes has to name
    them all.
    """
    prefixes = tuple(f"{axis}axis" for axis in axes)
    return [key for key in figure.layout.to_plotly_json() if key.startswith(prefixes)]


def _button_row(figure: go.Figure, buttons: list[dict]) -> go.Figure:
    """Put one row of relayout buttons above the top left of the figure, edited in place."""
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


def add_axis_scale_buttons(figure: go.Figure, axes: str = "x") -> go.Figure:
    """Add a linear/log button pair above the figure, switching every one of its axes at once.

    :param figure: The figure to add the buttons to, edited in place.
    :param axes: Which axes the buttons retype, ``x``, ``y`` or ``xy``.
    :return: The same figure.
    """
    names = _axis_names(figure, axes)
    buttons = [
        {
            "label": scale.capitalize(),
            "method": "relayout",
            "args": [{f"{name}.type": scale for name in names}],
        }
        for scale in ("linear", "log")
    ]
    return _button_row(figure, buttons)


#: The two measures the increment grid is coloured by, and the button label each carries.
INCREMENT_COLOUR_MEASURES = {
    "delta_cost_per_mwh_excl_fuel_carbon": "Delta cost (A$/MWh)",
    "delta_co2e_kt_per_yr": "Delta emissions (kt CO2e/yr)",
}

#: The level each arm of the L-shaped grid varies, against the level it holds at one.
INCREMENT_ARMS = {"demand_level": "intensity_level", "intensity_level": "demand_level"}

#: A level key names a percentage of the base cell's own, prefixed by the axis it varies: ``d135`` is
#: 1.35 times its demand and ``i010`` a tenth of its cap. The digits are the capture group.
INCREMENT_LEVEL_PATTERN = r"^[a-z](\d+)$"
INCREMENT_LEVEL_PER_CENT = 100.0

#: What every figure calls the base cell's own bar or line, beside the increment cells' labels.
BASE_CELL_LABEL = "base"


def increment_keys(rows: pd.DataFrame) -> pd.Series:
    """Each branch row's increment key, naming its two levels, e.g. ``d135_i050``."""
    return rows["demand_level"] + "_" + rows["intensity_level"]


def increment_label(key: str) -> str:
    """Spell out one increment key: ``d135_i050`` as ``d=1.35, i=0.50``, and the base cell as ``base``.

    :param key: An increment key, or ``base`` for the base cell itself.
    :return: The label every figure names that cell by.
    """
    if key == BASE_CELL_LABEL:
        return BASE_CELL_LABEL
    demand, intensity = (
        int(level[1:]) / INCREMENT_LEVEL_PER_CENT for level in key.split("_")
    )
    return f"d={demand:.2f}, i={intensity:.2f}"


#: Cost of the extra energy an increment cell delivers, and how the demand arm titles it.
INCREMENT_COST_PER_TWH = "delta_cost_per_extra_twh"
INCREMENT_COST_PER_TWH_LABEL = "Delta cost (A$/yr per extra TWh)"

#: What each cell of the grid says on hover: the two levels, the measure it is coloured by, and the
#: duals, intensity and new build its own row carries.
INCREMENT_HOVER = "d=%{x:.2f}, i=%{y:.2f}<br>%{z:.4g}<br>%{customdata}<extra></extra>"

#: Columns a cell's hover lists beside the measure it is coloured by.
INCREMENT_HOVER_COLUMNS = r"^fleet_intensity|^cap_dual_|^dual_|^delta_new_gw_"

#: The interior cells' own cost delta and the sum of their two arms, as the bars name each.
ADDITIVITY_SERIES = {
    "interior_aud_per_yr": "Interior cell",
    "additive_aud_per_yr": "Demand arm plus intensity arm",
}

#: Height of the increment section, which stacks three curve rows, the grids and the duals table.
INCREMENT_HEIGHT = 1450


def figure_increment_surfaces(increments: pd.DataFrame) -> go.Figure:
    """The increment grid: its two arms, the additivity check, and the whole grid per year.

    Each conditioned single-year solve is one cell, reported against the base cell it branched
    from. The demand arm prices extra energy at the base cell's cap, the intensity arm prices a
    deeper cap at the base cell's demand, each beside ShARP's approximate reference for the same
    step where one exists for that year, and the bars below test whether an interior cell costs
    what its two arms cost together, which is the additive form ShARP prices both through. The
    grids show every cell at once, annotated with each consequence, with the button switching their
    colouring between cost and emissions, and the table carries the implied carbon price each side
    of the increment faced.

    :param increments: The run's ``increments.csv``, one row per branch cell and year.
    """
    cells = _numeric_levels(increments.assign(increment=increment_keys(increments)))
    curves = _increment_curves(cells)
    blocks = [
        curves[curves["year"].eq(year)] for year in sorted(curves["year"].unique())
    ]
    figure = make_subplots(
        rows=5,
        cols=len(blocks),
        specs=_increment_specs(len(blocks)),
        subplot_titles=_increment_titles(blocks),
        vertical_spacing=0.06,
    )
    for block in blocks:
        for row, level in enumerate(INCREMENT_ARMS, start=1):
            arm = _increment_arm(block, level, row == 1)
            figure.add_trace(arm, row=row, col=1)
    for row, reference in _sharp_arms(curves):
        figure.add_trace(reference, row=row, col=1)
    for bar in _additivity_bars(cells):
        figure.add_trace(bar, row=3, col=1)
    for column, block in enumerate(blocks, start=1):
        figure.add_trace(_increment_heatmap(block), row=4, col=column)
    figure.add_trace(_cap_dual_table(cells), row=5, col=1)
    return _button_row(
        _label_increment_axes(figure), _increment_buttons(figure, blocks)
    )


def _numeric_levels(increments: pd.DataFrame) -> pd.DataFrame:
    """Each level key as the multiple of the base cell it names, e.g. ``d135`` as 1.35."""
    multiples = {
        level: pd.to_numeric(
            increments[level].astype(str).str.extract(INCREMENT_LEVEL_PATTERN)[0]
        )
        / INCREMENT_LEVEL_PER_CENT
        for level in INCREMENT_ARMS
    }
    return increments.assign(**multiples)


def _increment_curves(increments: pd.DataFrame) -> pd.DataFrame:
    """Increment cells with the demand arm's measure: cost per extra TWh delivered.

    A cell whose demand matches its base delivers no extra energy, so its ratio is left out
    rather than drawn as an infinite one.
    """
    per_twh = (
        increments["delta_total_cost_aud_per_yr"] / increments["delta_delivered_twh"]
    )
    return increments.assign(
        **{INCREMENT_COST_PER_TWH: per_twh.replace([np.inf, -np.inf], np.nan)}
    )


def _increment_specs(columns: int) -> list[list[dict | None]]:
    """Three full-width rows, the two arms and the additivity check, then the grids and the table."""
    wide = [[{"colspan": columns}, *[None] * (columns - 1)] for _ in range(3)]
    grids = [{} for _ in range(columns)]
    table = [{"colspan": columns, "type": "table"}, *[None] * (columns - 1)]
    return [*wide, grids, table]


def _increment_titles(blocks: list[pd.DataFrame]) -> list[str]:
    """Panel titles in subplot order: the arms, the additivity bars, each year's grid, the duals."""
    years = [str(block["year"].iloc[0]) for block in blocks]
    return [
        "Demand arm: cost of extra energy at the base cap",
        "Intensity arm: cost of a deeper cap at base demand",
        "Additivity check: each interior cell against its own two arms (A$m/yr)",
        *years,
        "Implied carbon price each side of the increment (A$/t)",
    ]


def _additivity_bars(increments: pd.DataFrame) -> list[go.Bar]:
    """Each interior cell's own cost delta beside the sum of its two arms, in A$m a year."""
    rows = _additivity_rows(increments)
    return [
        go.Bar(x=rows["label"], y=rows[column] / 1e6, name=name, legendgroup=name)
        for column, name in ADDITIVITY_SERIES.items()
    ]


def _additivity_rows(increments: pd.DataFrame) -> pd.DataFrame:
    """Interior cells against their arms: the cell's own delta, and its two arms' deltas summed."""
    interior = increments[
        increments["demand_level"].ne(1.0) & increments["intensity_level"].ne(1.0)
    ]
    arms = [
        _arm_at(interior, _arm_cost(increments, level), level)
        for level in INCREMENT_ARMS
    ]
    label = (
        interior["year"].astype(str) + ": " + interior["increment"].map(increment_label)
    )
    return pd.DataFrame(
        {
            "label": label.to_numpy(),
            "interior_aud_per_yr": interior["delta_total_cost_aud_per_yr"].to_numpy(),
            "additive_aud_per_yr": arms[0] + arms[1],
        }
    )


def _arm_cost(increments: pd.DataFrame, level: str) -> pd.Series:
    """Cost delta of one arm's cells, keyed on year and the level that arm varies."""
    arm = increments[increments[INCREMENT_ARMS[level]].eq(1.0)]
    return arm.set_index(["year", level])["delta_total_cost_aud_per_yr"]


def _arm_at(interior: pd.DataFrame, arm: pd.Series, level: str) -> np.ndarray:
    """One arm's cost delta at each interior cell's own year and level."""
    keys = pd.MultiIndex.from_arrays([interior["year"], interior[level]])
    return arm.reindex(keys).to_numpy()


def _increment_arm(block: pd.DataFrame, level: str, legend: bool) -> go.Scatter:
    """One year's arm of the L-shaped grid: the cells varying ``level``, the other held at one."""
    arm = block[block[INCREMENT_ARMS[level]].eq(1.0)].sort_values(level)
    measure = (
        INCREMENT_COST_PER_TWH
        if level == "demand_level"
        else "delta_cost_per_mwh_excl_fuel_carbon"
    )
    year = str(block["year"].iloc[0])
    return go.Scatter(
        x=arm[level],
        y=arm[measure],
        name=year,
        legendgroup=year,
        showlegend=legend,
        mode="lines+markers",
    )


def _sharp_arms(curves: pd.DataFrame) -> list[tuple[int, go.Scatter]]:
    """ShARP's reference on each arm row per year: the extra-MWh price on the demand arm, the clean ladder on the intensity arm."""
    traces = []
    for year, rows in _sharp_reference(curves["year"]).groupby("year"):
        arm = curves[curves["year"].eq(year) & curves["intensity_level"].eq(1.0)]
        demand = _sharp_demand_arm(rows, arm["demand_level"], not traces)
        traces += [(1, demand), (2, _sharp_intensity_arm(rows))]
    return traces


def _sharp_demand_arm(
    rows: pd.DataFrame, levels: pd.Series, legend: bool
) -> go.Scatter:
    """ShARP's approximate price of one extra MWh, flat across the demand arm, in A$ per extra TWh."""
    price = rows["extra_mwh_price_aud_per_mwh"].iloc[0] * MWH_PER_TWH
    label = f"{rows['year'].iloc[0]} extra-MWh price"
    return _sharp_line([levels.min(), levels.max()], [price, price], label, legend)


def _sharp_intensity_arm(rows: pd.DataFrame) -> go.Scatter:
    """ShARP's ladder cleaner than the planned share: intensity as a multiple of planned, cost above the planned share's."""
    planned = rows.iloc[0]
    cleaner = rows[
        rows["ladder_renewable_fraction"] > planned["planned_renewable_fraction"]
    ]
    x = cleaner["ladder_t_co2e_per_mwh"] / planned["planned_t_co2e_per_mwh"]
    y = (
        cleaner["ladder_cost_aud_per_mwh"]
        - planned["planned_share_ladder_cost_aud_per_mwh"]
    )
    label = f"{planned['year']} clean ladder"
    return _sharp_line([1.0, *x], [0.0, *y], label, False)


def _increment_grid(block: pd.DataFrame, measure: str) -> pd.DataFrame:
    """One year's cells on the exact grid they were solved on, demand across, intensity down."""
    return block.pivot(index="intensity_level", columns="demand_level", values=measure)


def _increment_heatmap(block: pd.DataFrame) -> go.Heatmap:
    """One year's grid, coloured by delta cost, annotated with each consequence, duals on hover."""
    cells = _increment_grid(block, next(iter(INCREMENT_COLOUR_MEASURES)))
    return go.Heatmap(
        x=cells.columns,
        y=cells.index,
        z=cells.to_numpy(),
        text=_increment_labels(block).to_numpy(),
        texttemplate="%{text}",
        textfont_size=9,
        customdata=_increment_hover_text(block).to_numpy(),
        coloraxis="coloraxis",
        hovertemplate=INCREMENT_HOVER,
    )


def _increment_labels(block: pd.DataFrame) -> pd.DataFrame:
    """Each cell's annotation: the cost, emissions and fuel consequence of that increment."""
    text = (
        (block["delta_total_cost_aud_per_yr"] / 1e6).map("A${:,.0f}m/yr".format)
        + block["delta_co2e_kt_per_yr"].map("<br>{:+,.0f} kt".format)
        + block["delta_pj_gas"].map("<br>gas {:+.1f} PJ".format)
        + block["delta_pj_coal"].map("<br>coal {:+.1f} PJ".format)
    )
    return _increment_grid(block.assign(label=text), "label")


def _increment_hover_text(block: pd.DataFrame) -> pd.DataFrame:
    """Each cell's hover: the intensity it reached, the duals both sides, and the new build."""
    shown = block.filter(regex=INCREMENT_HOVER_COLUMNS)
    text = shown.apply(
        lambda cell: "<br>".join(
            f"{name}: {value:,.4g}" for name, value in cell.items() if pd.notna(value)
        ),
        axis=1,
    )
    return _increment_grid(block.assign(hover=text), "hover")


def _increment_buttons(figure: go.Figure, blocks: list[pd.DataFrame]) -> list[dict]:
    """Switch every year's grid between the two increment measures at once."""
    grids = [
        index for index, trace in enumerate(figure.data) if trace.type == "heatmap"
    ]
    return [
        {
            "label": label,
            "method": "restyle",
            "args": [
                {"z": [_increment_grid(block, measure).to_numpy() for block in blocks]},
                grids,
            ],
        }
        for measure, label in INCREMENT_COLOUR_MEASURES.items()
    ]


def _label_increment_axes(figure: go.Figure) -> go.Figure:
    """Name each panel's axes and put every year's grid on one colour scale."""
    figure.update_xaxes(title_text=LABELS["demand_level"], row=1, col=1)
    figure.update_yaxes(title_text=INCREMENT_COST_PER_TWH_LABEL, row=1, col=1)
    figure.update_xaxes(title_text=LABELS["intensity_level"], row=2, col=1)
    figure.update_yaxes(title_text=LABELS["cost_per_mwh"], row=2, col=1)
    figure.update_yaxes(title_text=LABELS["delta_cost_aud_m_per_yr"], row=3, col=1)
    figure.update_xaxes(title_text=LABELS["demand_level"], row=4)
    figure.update_yaxes(title_text=LABELS["intensity_level"], row=4, col=1)
    colourbar = {
        "title": {"text": next(iter(INCREMENT_COLOUR_MEASURES.values()))},
        "len": 0.2,
    }
    return figure.update_layout(
        height=INCREMENT_HEIGHT,
        legend_title_text=LABELS["year"],
        coloraxis={"colorscale": "Viridis", "colorbar": colourbar},
    )


def _cap_dual_table(increments: pd.DataFrame) -> go.Table:
    """Implied carbon price each increment cell and its base cell faced, A$/t."""
    columns = ["cell", "year", "cap_dual_base", "cap_dual_branch"]
    shown = increments[columns].round(1)
    return go.Table(
        header={"values": columns}, cells={"values": [shown[c] for c in columns]}
    )


def figure_pathway_intensities(
    frame: pd.DataFrame, branches: pd.DataFrame | None = None
) -> go.Figure:
    """Conversion cost, emissions and fuel input intensity over the milestone years, one line per chain.

    The row mirrors the ShARP library's pathway intensities, so a modelled pathway reads beside a
    ShARP one: cost excludes fuel and carbon, and the input panel draws one dashed line per fuel.
    Every panel's line for a chain shares a legend group, so one legend click hides the chain across
    all three. The emissions panel carries the derived AEMO scenario intensities behind the chains as
    a sanity reference, and every panel carries ShARP's planned current-policy value, shaded out to
    its clean ladder's cleanest point, where the reference covers the plotted years.

    :param frame: The tidy cell-year frame of the campaign's base chains.
    :param branches: The increment grid's branch rows, each fanned out from the base point it
        branched from. A run with no increment grid draws the base chains alone.
    """
    figure = make_subplots(
        rows=1, cols=3, subplot_titles=[title for title, _ in INTENSITY_PANELS]
    )
    for reference in _aemo_overlay(_aemo_scenario_span(frame["year"].min())):
        figure.add_trace(reference, row=1, col=2)
    for column, references in enumerate(_sharp_pathway(frame["year"]), start=1):
        figure.add_traces(references, rows=1, cols=column)
    for key, colour in _increment_colours(branches).items():
        rows = branches[branches["increment"].eq(key)].sort_values("year")
        cost = _branch_fan(
            frame, rows, "cost_per_mwh_excl_fuel_carbon", colour, key, True
        )
        figure.add_trace(cost, row=1, col=1)
        figure.add_trace(
            _branch_fan(frame, rows, "fleet_intensity", colour, key), row=1, col=2
        )
        for column, (_, dash) in FUEL_INPUTS.items():
            if _fuel_burnt(rows, column):
                fan = _branch_fan(frame, rows, column, colour, key, dash=dash)
                figure.add_trace(fan, row=1, col=3)
    for cell, colour in _chain_colours(frame).items():
        chain = frame[frame["cell"].eq(cell)].sort_values("year")
        cost = chain["cost_per_mwh_excl_fuel_carbon"]
        figure.add_trace(_chain_line(chain, cost, colour, legend=True), row=1, col=1)
        emissions = _chain_line(chain, chain["fleet_intensity"], colour)
        figure.add_trace(emissions, row=1, col=2)
        for column, (fuel, dash) in FUEL_INPUTS.items():
            if _fuel_burnt(chain, column):
                inputs = _chain_line(chain, chain[column], colour, fuel, dash)
                figure.add_trace(inputs, row=1, col=3)
    figure.update_xaxes(
        title_text=LABELS["year"], tickvals=sorted(frame["year"].unique())
    )
    for column, (_, unit) in enumerate(INTENSITY_PANELS, start=1):
        figure.update_yaxes(title_text=unit, row=1, col=column)
    return figure.update_layout(
        height=INTENSITIES_HEIGHT,
        legend={"title_text": "Chain", "font_size": 10, "y": 1, "yanchor": "top"},
    )


def _aemo_scenario_span(first_year: int) -> pd.DataFrame:
    """The derived AEMO scenario intensities from ``first_year`` on, one column per scenario up the ambition ladder."""
    table = pd.read_csv(AEMO_INTENSITY_CSV)
    span = table.pivot(index="year", columns="scenario", values="t_co2e_per_mwh")
    return span.loc[span.index >= first_year, AEMO_SCENARIOS]


def _aemo_overlay(span: pd.DataFrame) -> list[go.Scatter]:
    """The shaded scenario range and one dotted line per scenario, in one legend group so a click hides the overlay."""
    shared = {
        "legendgroup": AEMO_LEGEND_GROUP,
        "mode": "lines",
        "x": span.index,
        "showlegend": True,
    }
    edge = {**shared, "line": {"width": 0}, "hoverinfo": "skip"}
    traces = [
        go.Scatter(**{**edge, "showlegend": False}, y=span.max(axis=1)),
        go.Scatter(
            **edge,
            y=span.min(axis=1),
            name="AEMO scenario range",
            fill="tonexty",
            fillcolor=AEMO_BAND_FILL,
        ),
    ]
    line = {"color": AEMO_LINE_COLOUR, "dash": "dot", "width": 1.5}
    for scenario in span:
        hover = f"AEMO {scenario}<br>%{{x}}: %{{y:.3g}}<extra></extra>"
        name = f"AEMO draft ISP: {scenario}"
        traces.append(
            go.Scatter(
                **shared, y=span[scenario], name=name, line=line, hovertemplate=hover
            )
        )
    return traces


def _sharp_reference(years: pd.Series) -> pd.DataFrame:
    """ShARP's reference rows for the years a figure plots, one per year and clean-ladder point."""
    table = pd.read_csv(SHARP_REFERENCE_CSV)
    return table[table["year"].isin(years)]


def _sharp_pathway(years: pd.Series) -> list[list[go.Scatter]]:
    """Per panel, ShARP's clean-ladder reach band behind its planned line, or nothing without matching years."""
    cleanest = _sharp_reference(years).drop_duplicates("year", keep="last")
    if cleanest.empty:
        return []
    return [
        [
            *_sharp_band(cleanest["year"], cleanest[column], reach, index == 0),
            _sharp_line(cleanest["year"], cleanest[column], "planned", index == 0),
        ]
        for index, (column, reach) in enumerate(
            zip(SHARP_PATHWAY_COLUMNS, _sharp_reach(cleanest))
        )
    ]


def _sharp_reach(cleanest: pd.DataFrame) -> list[pd.Series]:
    """The planned cost, emissions and fuel input moved to the cleanest ladder point, fuel scaling with the non-renewable share."""
    lift = (
        cleanest["ladder_cost_aud_per_mwh"]
        - cleanest["planned_share_ladder_cost_aud_per_mwh"]
    )
    residual = (1 - cleanest["ladder_renewable_fraction"]) / (
        1 - cleanest["planned_renewable_fraction"]
    )
    cost, emissions, inputs = (cleanest[column] for column in SHARP_PATHWAY_COLUMNS)
    return [cost + lift, emissions * residual, inputs * residual]


def _sharp_band(
    years: pd.Series, planned: pd.Series, reach: pd.Series, legend: bool
) -> list[go.Scatter]:
    """ShARP's clean-ladder reach shaded from the planned value to the cleanest point, under one legend entry."""
    edge = {
        "x": years,
        "mode": "lines",
        "line": {"width": 0},
        "hoverinfo": "skip",
        "legendgroup": SHARP_BAND_NAME,
    }
    return [
        go.Scatter(**edge, y=planned, showlegend=False),
        go.Scatter(
            **edge,
            y=reach,
            name=SHARP_BAND_NAME,
            showlegend=legend,
            fill="tonexty",
            fillcolor=SHARP_BAND_FILL,
        ),
    ]


def _sharp_line(
    x: list | pd.Series, y: list | pd.Series, label: str, legend: bool
) -> go.Scatter:
    """One dashed ShARP reference line, sharing a single legend entry with every other."""
    return go.Scatter(
        x=x,
        y=y,
        name=SHARP_NAME,
        legendgroup=SHARP_NAME,
        showlegend=legend,
        mode="lines+markers",
        line=SHARP_LINE,
        marker_size=4,
        hovertemplate=f"{SHARP_NAME}, {label}<br>%{{x:.3g}}: %{{y:.3g}}<extra></extra>",
    )


def _chain_colours(frame: pd.DataFrame) -> dict[str, str]:
    """One colour per chain, ordered trajectory-major and up the pressure ladder, cycling the palette."""
    orders = _orders(frame)
    chains = frame.drop_duplicates("cell").astype(
        {
            "trajectory": pd.CategoricalDtype(orders["trajectory"]),
            "pressure": pd.CategoricalDtype(orders["pressure"]),
        }
    )
    return dict(
        zip(
            chains.sort_values(["trajectory", "pressure"])["cell"],
            cycle(INPUT_COST_COLOURS),
        )
    )


def _chain_label(chain: pd.DataFrame) -> str:
    """Legend label for one chain: its demand trajectory and the pressure it was solved under."""
    row = chain.iloc[0]
    return f"{row['trajectory']} demand, {row['pressure_name']}"


def _chain_line(
    chain: pd.DataFrame,
    values: pd.Series,
    colour: str,
    fuel: str = "",
    dash: str = "solid",
    legend: bool = False,
) -> go.Scatter:
    """One chain's line in one intensity panel, named in the hover and grouped with its other panels."""
    label = _chain_label(chain)
    hover = ", ".join(filter(None, (label, fuel)))
    return go.Scatter(
        x=chain["year"],
        y=values,
        name=label,
        legendgroup=chain["cell"].iloc[0],
        showlegend=legend,
        mode="lines+markers",
        line={"color": colour, "dash": dash},
        marker_size=5,
        hovertemplate=f"{hover}<br>%{{x}}: %{{y:.3g}}<extra></extra>",
    )


def _fuel_burnt(chain: pd.DataFrame, column: str) -> bool:
    """Whether one chain burns a fuel in any milestone year, so the input panel draws its line."""
    return column in chain and chain[column].fillna(0).ne(0).any()


def _increment_colours(branches: pd.DataFrame | None) -> dict[str, str]:
    """One colour per increment cell key, demand-major, cycling the fan palette."""
    keys = sorted(branches["increment"].unique()) if branches is not None else []
    return dict(zip(keys, cycle(INCREMENT_FAN_COLOURS)))


def _fan_points(
    origins: pd.Series, rows: pd.DataFrame, column: str
) -> tuple[list, list]:
    """One increment key's fan: each branch value joined back to its base point one step earlier.

    A cell branching in the first milestone has no earlier base point, so it is drawn as a stub
    from the base point of its own year. ``None`` separates one segment from the next.
    """
    x: list = []
    y: list = []
    for row in rows.itertuples():
        start = row.year - BRANCH_STEP
        start = start if (row.base_cell, start) in origins.index else row.year
        x += [start, row.year, None]
        y += [origins[row.base_cell, start], getattr(row, column), None]
    return x, y


def _branch_fan(
    frame: pd.DataFrame,
    rows: pd.DataFrame,
    column: str,
    colour: str,
    key: str,
    legend: bool = False,
    dash: str = "solid",
) -> go.Scatter:
    """One increment key's fan in one intensity panel, thin and grouped with its other panels."""
    x, y = _fan_points(frame.set_index(["cell", "year"])[column], rows, column)
    label = increment_label(key)
    return go.Scatter(
        x=x,
        y=y,
        name=label,
        legendgroup=key,
        showlegend=legend,
        mode="lines+markers",
        line={"color": colour, "dash": dash, "width": 1},
        marker_size=4,
        connectgaps=False,
        hovertemplate=f"{label}<br>%{{x}}: %{{y:.3g}}<extra></extra>",
    )


def figure_demand_marginals(frame: pd.DataFrame) -> go.Figure | None:
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
    if long.empty:
        return None
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
    central = frame[
        frame["trajectory"].eq(_central_trajectory(list(frame["trajectory"])))
    ]
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


#: The premium columns of ``results.csv``, each titled as the page names that curve.
PREMIUM_LABELS = {
    "social_licence_premium_aud_per_yr": "Social licence (network)",
    "build_rate_premium_aud_per_yr": "Build rate",
}


def figure_premiums_paid(frame: pd.DataFrame) -> go.Figure | None:
    """What each cell-year paid for capacity above AEMO's published limits and baseline build rates.

    One stacked bar per cell and year, in A$ million a year. Nothing is drawn for a run launched
    without either curve, because every bar would be zero.
    """
    columns = [column for column in PREMIUM_LABELS if column in frame.columns]
    if not columns or not frame[columns].to_numpy().any():
        return None
    paid = frame.melt(
        id_vars=["cell", "year"],
        value_vars=columns,
        var_name="curve",
        value_name="premium_aud_per_yr",
    )
    figure = px.bar(
        paid.assign(
            curve=paid["curve"].map(PREMIUM_LABELS),
            premium_aud_m_per_yr=paid["premium_aud_per_yr"] / 1e6,
        ).astype({"year": str}),
        x="year",
        y="premium_aud_m_per_yr",
        color="curve",
        facet_col="cell",
        labels=LABELS,
        height=DECOMPOSITION_HEIGHT,
    )
    figure.update_xaxes(type="category")
    return _strip_facet_titles(figure)


#: Each kind of priced tranche as the page titles its curve, in panel order.
CURVE_LABELS = {
    "rez_resource": "REZ resource limit (curve 1a)",
    "transmission": "Network headroom (curve 1b)",
    "build_rate": "Build rate (curve 2)",
}

#: Columns every curve source is read into, in order.
CURVE_STEP_COLUMNS = ["curve", "group", "tranche", "width_mw", "adder", "mw_used"]

#: A REZ relaxation generator, e.g. ``N2_resource_limit_relax2_2035``: the resource limit it relaxes,
#: the tranche number, and the build year.
RELAX_PATTERN = r"^(.+)_relax(\d)_(\d{4})$"

#: How far past the steps below it an unbounded backstop tranche is drawn, as a share of their width.
BACKSTOP_SHARE = 0.5

#: Groups drawn per curve panel, widest first, so a run pricing dozens of links stays readable.
MOST_CURVE_GROUPS = 10

#: How the megawatts the base run bought on each step are marked.
CURVE_USAGE_NAME = "Megawatts the base run used"
CURVE_USAGE_COLOUR = "#1c1c1c"

#: Height of the build-curve figure, tall enough for one legend entry per group and period.
BUILD_CURVES_HEIGHT = 760


def tranche_curve_steps(tranches: pd.DataFrame) -> pd.DataFrame:
    """One solve's priced capacity tranches as curve steps, each group named with its period."""
    return tranches.assign(
        curve=tranches["kind"].map(CURVE_LABELS),
        group=tranches["group"] + " " + tranches["period"].astype(str),
    )[CURVE_STEP_COLUMNS]


def relax_curve_steps(generators: pd.DataFrame) -> pd.DataFrame:
    """One solve's REZ relaxation tranches as curve steps, one group per resource limit and period."""
    rows = generators[generators["name"].str.match(RELAX_PATTERN)]
    named = rows["name"].str.extract(RELAX_PATTERN)
    return pd.DataFrame(
        {
            "curve": CURVE_LABELS["rez_resource"],
            "group": named[0] + " " + named[2],
            "tranche": named[1].astype(int),
            "width_mw": rows["p_nom_max"].to_numpy(),
            "adder": rows["capital_cost"].to_numpy(),
            "mw_used": np.nan,
        }
    )


def build_rate_curve_steps(curve: pd.DataFrame) -> pd.DataFrame:
    """The authored build-rate curve as steps: its cumulative capacity caps as tranche widths."""
    rows = curve.sort_values(["group", "financial_year", "cap_mw"])
    caps = rows["cap_mw"].fillna(np.inf)
    keys = [rows["group"], rows["financial_year"]]
    return pd.DataFrame(
        {
            "curve": CURVE_LABELS["build_rate"],
            "group": rows["group"] + " " + rows["financial_year"].astype(str),
            "tranche": rows.groupby(keys).cumcount() + 1,
            "width_mw": caps.groupby(keys).diff().fillna(caps),
            "adder": rows["adder_$/mw/yr"],
            "mw_used": np.nan,
        }
    )


def figure_build_cost_curves(steps: pd.DataFrame) -> go.Figure:
    """Every priced build curve as a staircase of A$/MW/yr against cumulative megawatts.

    One panel per curve: the REZ resource-limit relaxation, the network headroom tranches and the
    per-carrier build rate, each group named with the period it priced. The marker on a step says
    how far into it the base run's own build reached, so a reader sees which tranche bound.

    :param steps: One row per tranche, from the run's own tranche records and curve inputs.
    """
    stairs = _cumulative_steps(_widest_curve_groups(steps))
    figure = px.line(
        stairs,
        x="cumulative_mw",
        y="adder",
        color="group",
        facet_col="curve",
        line_shape="hv",
        category_orders={"curve": list(CURVE_LABELS.values())},
        color_discrete_sequence=INPUT_COST_COLOURS,
        labels=LABELS,
        height=BUILD_CURVES_HEIGHT,
    )
    figure.update_xaxes(matches=None, showticklabels=True)
    figure.update_yaxes(matches=None, showticklabels=True)
    figure.update_layout(legend_title_text=LABELS["group"])
    return add_axis_scale_buttons(
        _mark_curve_usage(_strip_facet_titles(figure), stairs), axes="y"
    )


def _widest_curve_groups(
    steps: pd.DataFrame, most: int = MOST_CURVE_GROUPS
) -> pd.DataFrame:
    """The widest groups of each curve, so one panel does not draw dozens of links at once."""
    bounded = steps.assign(width_mw=_bounded_widths(steps, backstop=0.0))
    widest = (
        bounded.groupby(["curve", "group"])["width_mw"]
        .sum()
        .groupby("curve")
        .nlargest(most)
    )
    return steps[steps["group"].isin(widest.index.get_level_values("group"))]


def _cumulative_steps(steps: pd.DataFrame) -> pd.DataFrame:
    """Each group's tranches as staircase points: the cumulative megawatts each step's adder starts at.

    One closing point carries the last adder out to the end of its own tranche, so the staircase
    reads as the marginal cost curve it is rather than stopping at the last step's start.
    """
    ordered = steps.sort_values(["curve", "group", "tranche"])
    ordered = ordered.assign(width_mw=_bounded_widths(ordered))
    ends = ordered.assign(cumulative_mw=ordered.groupby("group")["width_mw"].cumsum())
    starts = ends.assign(cumulative_mw=ends["cumulative_mw"] - ends["width_mw"])
    closing = ends.groupby("group").tail(1).assign(mw_used=np.nan)
    return pd.concat([starts, closing]).sort_values(["group", "cumulative_mw"])


def _bounded_widths(steps: pd.DataFrame, backstop: float = BACKSTOP_SHARE) -> pd.Series:
    """Tranche widths with an unbounded backstop drawn as a share again of the steps below it."""
    widths = steps["width_mw"]
    bounded = widths.where(np.isfinite(widths), 0.0)
    drawn = bounded.groupby(steps["group"]).transform("sum") * backstop
    return widths.where(np.isfinite(widths), drawn)


def _mark_curve_usage(figure: go.Figure, stairs: pd.DataFrame) -> go.Figure:
    """Mark how far into each step the base run's own build reached, one panel at a time."""
    panels = [curve for curve in CURVE_LABELS.values() if curve in set(stairs["curve"])]
    for panel, curve in enumerate(panels, start=1):
        used = stairs[stairs["curve"].eq(curve) & stairs["mw_used"].gt(0)]
        figure.add_scatter(
            x=used["cumulative_mw"] + used["mw_used"],
            y=used["adder"],
            name=CURVE_USAGE_NAME,
            mode="markers",
            marker={"symbol": "diamond", "size": 8, "color": CURVE_USAGE_COLOUR},
            legendgroup="used",
            showlegend=panel == 1,
            row=1,
            col=panel,
        )
    return figure


#: AEMO's draft 2026 ISP Step Change candidate development path 4 (CDP4) installed capacity, in GW
#: by fuel and calendar year, tracked beside the other CDP4 exports this repository carries.
CDP4_CAPACITY_CSV = (
    REPO_ROOT / "iasr outputs" / "NEM-aemo2026draft-step_change-CDP4 (ODP)-capacity.csv"
)

#: The year the near term is pinned to, and the carriers that figure compares, in bar order.
PIPELINE_YEAR = 2030
PIPELINE_CARRIERS = ["Coal", "Gas", "Hydro", "Wind", "Solar", "Battery"]

#: Model carriers and CDP4 fuel columns mapped onto those carriers. A carrier only one side names,
#: biomass and liquid fuel, is left out rather than stacked against nothing.
PIPELINE_CARRIER_NAMES = {
    "Black Coal": "Coal",
    "Brown Coal": "Coal",
    "Gas": "Gas",
    "Water": "Hydro",
    "Wind": "Wind",
    "Solar": "Solar",
    "Battery": "Battery",
}
CDP4_CARRIER_NAMES = {
    "Coal": "Coal",
    "Gas": "Gas",
    "Hydro": "Hydro",
    "Wind": "Wind",
    "Solar (Utility)": "Solar",
}

#: The fleet segments stacked, in stacking order, and the reference dashed beside them.
PIPELINE_SEGMENTS = ["Existing", "Committed and anticipated", "New build"]
AEMO_CAPACITY_SEGMENT = f"AEMO CDP4 {PIPELINE_YEAR}"

#: The near-term allowances drawn as dashed lines, each keyed on the plan value it is read from.
ALLOWANCE_LABELS = {
    "new_entrant_cap_mw": "New-entrant generator allowance",
    "new_entrant_storage_cap_mw": "New-entrant storage allowance",
}


def figure_near_term_pipeline(
    roster: pd.DataFrame, built: pd.DataFrame, allowances: dict[str, float]
) -> go.Figure:
    """Capacity by carrier in the pinned year: the pipeline, the new build, and AEMO's own fleet.

    The stack is what the near-term pin holds, the existing fleet and the committed and anticipated
    projects of the roster, with the capacity the solve built new on top. The dash beside each stack
    is AEMO's CDP4 capacity for the same year, and each dashed line is a NEM-wide new-entrant
    allowance the run was launched with.

    :param roster: The base solve's ECAA generator and battery tables for the pinned year.
    :param built: The base rows of ``results.csv`` for the pinned year, with their ``new_gw_`` columns.
    :param allowances: Allowance name to its NEM-wide ceiling in GW.
    """
    fleet = pd.concat([_roster_capacity(roster), _new_build_capacity(built)])
    figure = px.bar(
        fleet,
        x="carrier",
        y="gw",
        color="segment",
        category_orders={"carrier": PIPELINE_CARRIERS, "segment": PIPELINE_SEGMENTS},
        labels=LABELS,
        height=DECOMPOSITION_HEIGHT,
    )
    _mark_aemo_capacity(figure, _aemo_capacity())
    for name, gw in allowances.items():
        figure.add_hline(
            y=gw,
            line={"dash": "dash", "width": 1},
            annotation_text=f"{name}: {gw:g} GW",
        )
    return figure.update_layout(legend_title_text=LABELS["segment"])


def _roster_capacity(roster: pd.DataFrame) -> pd.DataFrame:
    """Existing and pipeline capacity per carrier in GW, from one solve's ECAA rosters."""
    named = roster.assign(
        carrier=roster["fuel_type"].map(PIPELINE_CARRIER_NAMES),
        segment=_pipeline_segment(roster["status"]),
    ).dropna(subset=["carrier", "segment"])
    grouped = named.groupby(["carrier", "segment"], as_index=False)[
        "maximum_capacity_mw"
    ].sum()
    return grouped.assign(gw=grouped["maximum_capacity_mw"] / 1e3)


def _pipeline_segment(status: pd.Series) -> pd.Series:
    """Fleet segment one ECAA status belongs to: the existing fleet, or the committed pipeline."""
    pipeline = status.where(status.eq(PIPELINE_SEGMENTS[0]), PIPELINE_SEGMENTS[1])
    return pipeline.where(status.ne("New Entrant"))


def _new_build_capacity(built: pd.DataFrame) -> pd.DataFrame:
    """Capacity the base solve built new in the pinned year, in GW per carrier."""
    new = built.filter(regex=r"^new_gw_").rename(
        columns=lambda column: column.removeprefix("new_gw_")
    )
    carriers = new.sum().rename(PIPELINE_CARRIER_NAMES).groupby(level=0).sum()
    kept = carriers[carriers.index.isin(PIPELINE_CARRIERS)]
    return pd.DataFrame(
        {"carrier": kept.index, "segment": PIPELINE_SEGMENTS[2], "gw": kept.to_numpy()}
    )


def _aemo_capacity() -> pd.DataFrame:
    """AEMO's own CDP4 installed capacity in the pinned year, GW per carrier the figure compares."""
    table = pd.read_csv(CDP4_CAPACITY_CSV)
    row = table[table["date"].str.contains(str(PIPELINE_YEAR))].iloc[0]
    gw = row[list(CDP4_CARRIER_NAMES)].astype(float).rename(CDP4_CARRIER_NAMES)
    return pd.DataFrame({"carrier": gw.index, "gw": gw.to_numpy()})


def _mark_aemo_capacity(figure: go.Figure, aemo: pd.DataFrame) -> go.Figure:
    """Dash AEMO's own capacity for the pinned year above each carrier's stack."""
    return figure.add_scatter(
        x=aemo["carrier"],
        y=aemo["gw"],
        name=AEMO_CAPACITY_SEGMENT,
        mode="markers",
        marker_symbol="line-ew",
        marker_size=LIMIT_MARKER_SIZE,
        marker_line={"color": UNSERVED_COLOUR, "width": LIMIT_MARKER_WIDTH},
    )


#: The two duals panels in page order, and the columns the table lists.
DUAL_PANEL_TITLES = [
    "Implied carbon price of each cell's cap (A$/t)",
    "Largest custom-constraint duals of the base chain, per year",
]
DUAL_TABLE_COLUMNS = ["year", "constraint", "dual"]

#: Constraint duals listed per year, the largest by absolute value first.
MOST_DUALS_PER_YEAR = 10

#: Height of the duals section, which stacks a bar panel over a table.
DUALS_HEIGHT = 820


def figure_duals(manifest: pd.DataFrame, duals: pd.DataFrame) -> go.Figure:
    """The shadow price each cell's cap carried, and the base chain's largest constraint duals.

    :param manifest: The run's ``manifest.csv``, one row per cell and year.
    :param duals: The base chain's exported duals, one row per constraint, cell and year.
    """
    figure = make_subplots(
        rows=2,
        cols=1,
        specs=[[{}], [{"type": "table"}]],
        subplot_titles=DUAL_PANEL_TITLES,
        vertical_spacing=0.12,
    )
    priced = manifest.dropna(subset=["implied_carbon_price_aud_per_t"]).astype(
        {"year": str}
    )
    for cell, block in priced.groupby("cell"):
        figure.add_bar(
            x=block["year"],
            y=block["implied_carbon_price_aud_per_t"],
            name=cell,
            row=1,
            col=1,
        )
    figure.add_trace(_largest_dual_table(duals), row=2, col=1)
    figure.update_yaxes(
        title_text=LABELS["implied_carbon_price_aud_per_t"], row=1, col=1
    )
    return figure.update_layout(
        height=DUALS_HEIGHT, barmode="group", legend_title_text="Cell"
    )


def _largest_dual_table(duals: pd.DataFrame) -> go.Table:
    """The largest constraint duals of each year, by absolute value, largest first."""
    ranked = duals.assign(size=duals["dual"].abs()).sort_values(
        ["year", "size"], ascending=[True, False]
    )
    shown = ranked.groupby("year").head(MOST_DUALS_PER_YEAR).round({"dual": 1})
    return go.Table(
        header={"values": DUAL_TABLE_COLUMNS},
        cells={"values": [shown[column] for column in DUAL_TABLE_COLUMNS]},
    )


def figure_input_costs(costs: pd.DataFrame) -> go.Figure:
    """The cost inputs the run's solves were templated from, over the financial years they cover.

    One panel per cost category, each on its own y scale because the categories are priced in
    different units. Build cost spans more than an order of magnitude across the technologies, so
    that panel is drawn logarithmically; the buttons above switch every panel between the two
    scales. A cost input named after a generation carrier takes that carrier's colour, so biomass,
    gas and wind read here as they do everywhere else on the page.

    :param costs: The run's ``input_costs.csv``, one row per category, name and year.
    """
    drawn = costs.dropna(subset=["value"])
    panels = [name for name in INPUT_COST_LABELS if name in set(drawn["category"])]
    figure = px.line(
        drawn.replace({"category": INPUT_COST_LABELS}).sort_values(["name", "year"]),
        x="year",
        y="value",
        color="name",
        facet_col="category",
        category_orders={"category": [INPUT_COST_LABELS[name] for name in panels]},
        color_discrete_map=_carrier_named_colours(drawn["name"]),
        color_discrete_sequence=INPUT_COST_COLOURS,
        labels=LABELS,
        height=INPUT_COSTS_HEIGHT,
    )
    figure.update_yaxes(matches=None, showticklabels=True)
    if "build_cost" in panels:
        figure.update_yaxes(type="log", col=panels.index("build_cost") + 1)
    figure.update_layout(legend_title_text="Cost input")
    return add_axis_scale_buttons(_strip_facet_titles(figure), axes="y")


def _carrier_named_colours(names: pd.Series) -> dict[str, str]:
    """Pin the cost inputs named after a generation carrier to that carrier's colour."""
    return {
        name: CARRIER_COLOURS[name]
        for name in names.unique()
        if name in CARRIER_COLOURS
    }


#: Styling shared by every html table on the page: full page width, small text, sortable headings.
GRID_STYLE = """<style>
.grid { width: 100%; border-collapse: collapse; font-size: 12px; text-align: left }
.grid th { cursor: pointer; text-align: left; border-bottom: 1px solid #bbb }
.grid th::after { content: " ^" }
.grid td { padding: 2px 4px; border: 1px solid #eee }
</style>"""


def figure_tech_mix(
    frame: pd.DataFrame, branches: pd.DataFrame | None = None
) -> go.Figure:
    """Stacked energy delivered by carrier, in TWh, the base cell then each increment cell, per year.

    Demand no generation served is stacked last, in red, so the shortfall a deep cap leaves reads off
    the top of the stack. Cells that failed acceptance are drawn hatched rather than dropped, so a
    reader sees where the campaign has a mix it cannot stand behind instead of an unexplained gap.
    Storage discharge stacks above the generation carriers, dotted, and is energy the storage charged
    from them rather than new supply, so a stack carrying it exceeds the year's demand.

    :param frame: The tidy cell-year frame of the campaign's base chains.
    :param branches: The increment grid's branch rows. A run with no increment grid bars the base
        cell alone.
    """
    long = _delivered_energy(_labelled_cells(frame, branches))
    figure = px.bar(
        long.astype({"year": str}),
        x="cell_label",
        y="twh",
        color="carrier",
        pattern_shape="pattern",
        pattern_shape_map=MIX_PATTERNS,
        facet_col="year",
        category_orders={"carrier": [*CARRIER_COLOURS, UNSERVED_CARRIER]},
        color_discrete_map={**CARRIER_COLOURS, UNSERVED_CARRIER: UNSERVED_COLOUR},
        labels=LABELS,
        height=DECOMPOSITION_HEIGHT,
    )
    figure.update_xaxes(type="category")
    figure.update_layout(legend_title_text="Carrier")
    _colour_legend_entries(figure)
    _strip_facet_titles(figure)
    return _pattern_note(figure, HATCH_NOTE, long["carrier"].nunique())


def _labelled_cells(frame: pd.DataFrame, branches: pd.DataFrame | None) -> pd.DataFrame:
    """The base chain's rows and the increment cells' rows, each labelled as the bars name it.

    Sorted on the label, which puts the base cell's bar first and then runs the increment cells
    demand-major up each level, because plotly bars them in the order it meets them.
    """
    base = frame.assign(cell_label=BASE_CELL_LABEL)
    if branches is None or branches.empty:
        return base
    labelled = branches.assign(cell_label=branches["increment"].map(increment_label))
    return pd.concat([base, labelled], ignore_index=True).sort_values("cell_label")


def _delivered_energy(cells: pd.DataFrame) -> pd.DataFrame:
    """Melt the per-carrier energy columns into one row each, unserved energy last.

    Unserved energy is taken from the shortfall percentage the run reported against its demand. A
    storage discharge column is patterned as storage instead of by the cell's status.
    """
    keys = ["cell_label", "year", "status"]
    carriers = cells[keys].join(cells.filter(regex=r"^twh_"))
    long = carriers.melt(id_vars=keys, var_name="carrier", value_name="twh")
    long["carrier"] = long["carrier"].str.removeprefix("twh_").replace(CARRIER_LABELS)
    unserved = cells[keys].assign(
        carrier=UNSERVED_CARRIER,
        twh=cells["delivered_twh"] * cells["use_pct_of_demand"] / 100,
    )
    mix = pd.concat([long, unserved], ignore_index=True)
    mix["pattern"] = mix["status"].mask(
        mix["carrier"].isin(STORAGE_PATTERNS), "storage"
    )
    return mix


def figure_storage_build(
    frame: pd.DataFrame, branches: pd.DataFrame | None = None
) -> go.Figure:
    """Installed storage power by duration class, the base cell then each increment cell, per year.

    Battery and pumped hydro share the duration colours and are told apart by hatching, so the
    figure reads as one storage stack rather than two.

    :param frame: The tidy cell-year frame of the campaign's base chains.
    :param branches: The increment grid's branch rows. A run with no increment grid bars the base
        cell alone.
    """
    long = _storage_rows(_labelled_cells(frame, branches))
    figure = px.bar(
        long.astype({"year": str}),
        x="cell_label",
        y="power_gw",
        color="duration_class",
        pattern_shape="carrier",
        pattern_shape_map=STORAGE_PATTERNS,
        facet_col="year",
        category_orders={
            "duration_class": list(DURATION_LABELS.values()),
            "carrier": list(STORAGE_PATTERNS),
        },
        labels=LABELS,
        height=DECOMPOSITION_HEIGHT,
    )
    figure.update_xaxes(type="category")
    figure.update_layout(legend_title_text=LABELS["duration_class"])
    _colour_legend_entries(figure)
    _strip_facet_titles(figure)
    return _pattern_note(figure, STORAGE_NOTE, long["duration_class"].nunique())


def _storage_rows(cells: pd.DataFrame) -> pd.DataFrame:
    """Melt the per-carrier, per-duration storage power columns back into one row each."""
    long = cells.melt(
        id_vars=["cell_label", "year"],
        value_vars=list(cells.filter(regex=r"^storage_")),
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


#: The transmission panels in page order, each titled as the page names that class of link.
LINK_KIND_LABELS = {
    "rez": "REZ connections",
    "flow_path": "Sub-region flow paths",
}

#: The ceilings each panel marks above its bars, each named and coloured as it is drawn.
LIMIT_MARKERS = {
    "aemo_limit_mw": ("AEMO IASR limit", "#1c1c1c"),
    "tranche_2_limit_mw": ("2x AEMO limit (premium step)", "#ff7f0e"),
    "relaxed_limit_mw": ("Relaxed limit", "#d62728"),
}

#: The two priced tranches, each shaded between the limits it sits between, named and filled as it
#: is drawn. The first is a second helping of published headroom at the first social-licence
#: premium; the second runs from there to the run's hard ceiling at the second premium.
TRANCHE_BANDS = {
    ("aemo_limit_mw", "tranche_2_limit_mw"): (
        "First premium tranche",
        "rgba(255,127,14,0.18)",
    ),
    ("tranche_2_limit_mw", "relaxed_limit_mw"): (
        "Second premium tranche",
        "rgba(214,39,40,0.14)",
    ),
}

#: Milestone-year bar hues, a single-hue ramp light to dark so the years read in time order and
#: neither collides with the colours the two limit dashes are drawn in.
TRANSMISSION_YEAR_COLOURS = px.colors.sequential.Blues[3:]

#: Width and thickness of a limit dash, in pixels. Wide enough to span a link's whole bar group.
LIMIT_MARKER_SIZE = 26
LIMIT_MARKER_WIDTH = 3

#: Height of the transmission figure, in pixels. Taller than the other single-strip figures because
#: its x labels are link names rotated under the axis.
TRANSMISSION_HEIGHT = 560


def figure_transmission_limits(
    links: pd.DataFrame, rez_factor: float, flow_path_factor: float
) -> go.Figure:
    """Capacity built on each REZ connection and flow path against the two ceilings it faced.

    One panel per class of link, for the central-demand chain at the run's deepest cap: the chain
    most likely to be pressed against its network ceilings. Bars are the capacity each milestone
    solved to, and the two dashes above them are AEMO's published limit and the relaxed limit the
    run actually allowed. A REZ connection with no published transmission limit carries ISPyPSA's
    unlimited placeholder capacity instead of a ceiling, so it is left out.

    :param links: The run's ``transmission.csv``, one row per cell, year and link.
    :param rez_factor: Factor the run relaxed the REZ limits by.
    :param flow_path_factor: Factor the run relaxed the flow-path expansion limits by.
    """
    cell = _deepest_central_cell(links)
    limited = links["kind"].eq("flow_path") | links["transmission_limit_mw"].notna()
    drawn = _limit_columns(
        links[links["cell"].eq(cell) & limited],
        {"rez": rez_factor, "flow_path": flow_path_factor},
    ).sort_values("aemo_limit_mw", ascending=False)
    figure = px.bar(
        drawn.astype({"year": str}).replace({"kind": LINK_KIND_LABELS}),
        x="link",
        y="p_nom_opt_mw",
        color="year",
        barmode="group",
        facet_col="kind",
        category_orders={
            "year": sorted(drawn["year"].unique().astype(str)),
            "kind": list(LINK_KIND_LABELS.values()),
        },
        color_discrete_sequence=TRANSMISSION_YEAR_COLOURS,
        labels=LABELS,
        height=TRANSMISSION_HEIGHT,
        title=f"Central demand at the run's deepest cap: {cell}",
    )
    figure.update_xaxes(matches=None, showticklabels=True, type="category")
    figure.update_layout(legend_title_text=LABELS["year"], bargroupgap=0.05)
    shaded = _shade_priced_tranches(_strip_facet_titles(figure), drawn)
    return _add_limit_markers(shaded, drawn)


def _deepest_central_cell(links: pd.DataFrame) -> str:
    """The central-demand chain at the run's deepest cap, the one cell the panels draw."""
    trajectories = [split_chain_id(cell)[0] for cell in links["cell"].unique()]
    central = _central_trajectory(trajectories)
    pressures = [
        split_chain_id(cell)[1]
        for cell in links["cell"].unique()
        if split_chain_id(cell)[0] == central
    ]
    return f"ext_{central}_{order_pressures(pressures)[-1].key}"


def _central_trajectory(trajectories: list[str]) -> str:
    """The one demand trajectory the single-chain figures draw.

    The campaign's own central trajectory where it has one, and otherwise the median of the
    base trajectories. An increment-grid branch extends the key of the base trajectory it
    branched from, so it is never the trajectory drawn.
    """
    keys = sorted(set(trajectories))
    bases = [key for key in keys if not any(key.startswith(f"{k}_") for k in keys)]
    return CENTRAL_TRAJECTORY if CENTRAL_TRAJECTORY in bases else bases[len(bases) // 2]


def _limit_columns(links: pd.DataFrame, factors: dict[str, float]) -> pd.DataFrame:
    """Add each link's relaxed ceiling, the IASR ceiling it was relaxed from, and the premium step.

    A REZ connection's templated capacity is itself a relaxed transmission limit, so both halves of
    its ceiling divide by the REZ factor. A flow path keeps AEMO's own corridor capacity and only
    its expansion headroom was relaxed, so only that half divides. The premium step is where a
    second helping of published headroom runs out and the priced tranches take over.
    """
    headroom = links["expansion_limit_mw"].fillna(0)
    factor = links["kind"].map(factors)
    relaxed = links["p_nom_mw"] + headroom
    return links.assign(
        relaxed_limit_mw=relaxed,
        aemo_limit_mw=np.where(
            links["kind"].eq("rez"),
            relaxed / factor,
            links["p_nom_mw"] + headroom / factor,
        ),
        tranche_2_limit_mw=np.where(
            links["kind"].eq("rez"),
            (links["p_nom_mw"] + 2 * headroom) / factor,
            links["p_nom_mw"] + 2 * headroom / factor,
        ),
    )


def _shade_priced_tranches(figure: go.Figure, drawn: pd.DataFrame) -> go.Figure:
    """Shade each panel between the published limit, the premium step and the hard ceiling.

    The bands are moved ahead of the bars so the capacity built reads against them rather than
    under them.
    """
    panels = [kind for kind in LINK_KIND_LABELS if kind in set(drawn["kind"])]
    for (panel, kind), (columns, band) in product(
        enumerate(panels, start=1), TRANCHE_BANDS.items()
    ):
        block = drawn[drawn["kind"].eq(kind)].drop_duplicates("link")
        _add_tranche_band(figure, block, columns, band, panel)
    figure.data = tuple(sorted(figure.data, key=lambda trace: trace.type == "bar"))
    return figure


def _add_tranche_band(
    figure: go.Figure,
    block: pd.DataFrame,
    columns: tuple[str, str],
    band: tuple[str, str],
    panel: int,
) -> None:
    """Fill one panel between two per-link limits: a stepped floor, then the ceiling filled down to it."""
    name, fill = band
    for column, area in zip(columns, (None, "tonexty")):
        figure.add_scatter(
            x=block["link"],
            y=block[column],
            name=name,
            mode="lines",
            line={"width": 0, "shape": "hv"},
            fill=area,
            fillcolor=fill,
            legendgroup=name,
            legendgrouptitle_text="Priced tranche",
            showlegend=area is not None and panel == 1,
            hoverinfo="skip",
            row=1,
            col=panel,
        )


def _add_limit_markers(figure: go.Figure, drawn: pd.DataFrame) -> go.Figure:
    """Mark both ceilings on every panel, one dash per link, listed once in the legend."""
    panels = [kind for kind in LINK_KIND_LABELS if kind in set(drawn["kind"])]
    for (panel, kind), (column, (name, colour)) in product(
        enumerate(panels, start=1), LIMIT_MARKERS.items()
    ):
        block = drawn[drawn["kind"].eq(kind)].drop_duplicates("link")
        figure.add_scatter(
            x=block["link"],
            y=block[column],
            name=name,
            mode="markers",
            marker_symbol="line-ew",
            marker_size=LIMIT_MARKER_SIZE,
            marker_line={"color": colour, "width": LIMIT_MARKER_WIDTH},
            legendgroup="limits",
            legendgrouptitle_text="Limit",
            showlegend=panel == 1,
            row=1,
            col=panel,
        )
    return figure
