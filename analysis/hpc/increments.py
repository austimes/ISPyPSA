"""The increment grid: one conditioned single-year solve per (snapshot year, demand, intensity) cell.

At each milestone year the base chain reports one point. The grid asks what a step in demand or a
step in carbon pressure costs at that point, by re-solving the year on its own with the base stock
pinned, the base state seeded in, and the annual cap set by the cell. The cells are L-shaped: a pure
demand column at the base intensity, a pure intensity row at the base demand, and a few interior
cells that test whether the two add.

The plan's ``increment_grid`` block holds the levels and the cells; each cell's demand level scales
the base trajectory's load for that year, so every (year, demand level) pair is its own single-knot
demand trajectory, ``<base trajectory>_b<year>_d<level>``. Those trajectories live under
``increment_demand_paths_source_twh`` and never under ``demand_paths_source_twh``, which carries the
base trajectories the marginals ladder is computed across.
"""

from __future__ import annotations

from dataclasses import dataclass

GRID_KEY = "increment_grid"
INCREMENT_PATHS_KEY = "increment_demand_paths_source_twh"


@dataclass(frozen=True)
class Cell:
    """One increment solve: a snapshot year at one demand level and one intensity level.

    :param trajectory: Single-knot demand trajectory the cell is solved on.
    :param year: Snapshot year, the cell's only period.
    :param demand_level: Level key, e.g. ``d110``.
    :param demand_factor: Multiple of the base trajectory's load for that year.
    :param intensity_level: Level key, e.g. ``i050``.
    :param intensity_factor: Multiple of the base chain's cap intensity for that year.
    :param source_twh: The cell's own source NEM load in TWh.
    """

    trajectory: str
    year: int
    demand_level: str
    demand_factor: float
    intensity_level: str
    intensity_factor: float
    source_twh: float


def base_trajectory(plan: dict) -> tuple[str, dict[str, float]]:
    """The plan's single base trajectory: its name and its authored source-TWh knots."""
    ((name, knots),) = plan["demand_paths_source_twh"].items()
    return name, knots


def _cell(plan: dict, year: int, demand_level: str, intensity_level: str) -> Cell:
    """Assemble one grid cell from its two level keys at one milestone year."""
    grid = plan[GRID_KEY]
    name, knots = base_trajectory(plan)
    demand_factor = grid["demand_levels"][demand_level]
    return Cell(
        trajectory=f"{name}_b{year}_{demand_level}",
        year=year,
        demand_level=demand_level,
        demand_factor=demand_factor,
        intensity_level=intensity_level,
        intensity_factor=grid["intensity_levels"][intensity_level],
        source_twh=knots[str(year)] * demand_factor,
    )


def cells(plan: dict) -> list[Cell]:
    """Every increment cell of the plan, grouped by milestone year; empty without a grid."""
    if GRID_KEY not in plan:
        return []
    return [
        _cell(plan, year, demand_level, intensity_level)
        for year in plan["milestone_years"]
        for demand_level, intensity_level in plan[GRID_KEY]["cells"]
    ]


def demand_paths(plan: dict) -> dict[str, dict[str, float]]:
    """Single-knot demand trajectories of the grid, one per (milestone year, demand level)."""
    return {cell.trajectory: {str(cell.year): cell.source_twh} for cell in cells(plan)}


def expand(plan: dict) -> dict:
    """The plan with its increment demand trajectories written in, as the launch records them."""
    return plan | {INCREMENT_PATHS_KEY: demand_paths(plan)}
