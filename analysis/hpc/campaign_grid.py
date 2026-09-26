"""The two axes of the extension campaign: demand trajectories and pressure settings.

The campaign is a grid of recursive-dynamic chains, one per (demand trajectory,
pressure setting), named ``ext_<trajectory>_<pressure>``. This module is the single
place that knows how those names decompose, how each axis is labelled for a reader,
and what order the two axes are presented in. Both the deliverables builder and the
dashboard data builder read the axes from here so a chain is never labelled two ways.

Pressure keys come in three families:

* ``c<N>`` -- a carbon price of A$N per tonne CO2e, held constant along the chain.
  ``c0`` is the uncapped incumbent.
* ``cap<digits>`` -- an absolute annual CO2e cap, named by its target intensity in t/MWh
  with the leading ``0.`` stripped: ``cap002`` is 0.02 t/MWh, ``cap00005`` is 0.0005 t/MWh.
* ``sc`` -- the Step Change base chain, whose cap follows the scenario's own intensity path
  and so carries no single target intensity.

Presentation order runs the prices cheapest to dearest, then the caps shallow to
deep, which is the order of increasing decarbonisation pressure within each family.
The two families are not commensurable -- a cap's stringency is only revealed by the
shadow price its solve reports -- so they are never interleaved.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from analysis.hpc import increments

PRICE_KIND = "price"
CAP_KIND = "cap"

# The Step Change base chain's cap follows the scenario's own intensity path, so it is named
# for the scenario rather than for a single target intensity.
BASE_CHAIN_KEY = "sc"

_CHAIN_PREFIX = "ext_"
_TRAJECTORY_PREFIX = "iasr_"


@dataclass(frozen=True)
class Pressure:
    """One pressure setting of the ladder.

    :param key: Chain-id suffix, e.g. ``c150`` or ``cap0005``.
    :param label: Reader-facing label, e.g. ``A$150/t`` or ``cap 0.005``.
    :param short: Compact label for a crowded axis, e.g. ``$150`` or ``.005``.
    :param kind: ``price`` or ``cap``.
    :param value: Carbon price in A$/t for a price chain, 2050 target intensity in
        t CO2e/MWh delivered for a cap chain.
    """

    key: str
    label: str
    short: str
    kind: str
    value: float

    @property
    def carbon_price(self) -> float:
        """Carbon price the solve was run at. A cap chain prices carbon at zero and
        exerts its pressure through the cap constraint instead."""
        return self.value if self.kind == PRICE_KIND else 0.0


@dataclass(frozen=True)
class Trajectory:
    """One demand trajectory of the campaign.

    :param key: Chain-id segment, e.g. ``low_bracket``.
    :param label: Reader-facing label, e.g. ``Low bracket``.
    :param source_twh: Source NEM load in TWh per milestone year, from the demand plan.
    """

    key: str
    label: str
    source_twh: dict[int, float]

    @property
    def peak_source_twh(self) -> float:
        """Largest source load on the trajectory, used to order the axis."""
        return max(self.source_twh.values())


def cap_key(intensity: float) -> str:
    """Chain key for a cap intensity, the inverse of :func:`parse_pressure`: 0.0645 -> ``cap00645``.

    The intensity is rounded to six significant figures and written in positional notation, so
    0.00006925 is ``cap000006925`` rather than an exponent.
    """
    return "cap" + format(Decimal(f"{intensity:g}"), "f").replace(".", "")


def parse_pressure(key: str) -> Pressure:
    """Decompose one pressure key into its family, value and labels.

    :param key: ``c<N>`` for a carbon price, ``cap<digits>`` for a cap schedule, or ``sc`` for
        the Step Change base chain, whose cap follows the scenario's own intensity path and so
        has no single target intensity.
    :return: The parsed pressure.
    :raises ValueError: If the key belongs to no family.
    """
    if key == BASE_CHAIN_KEY:
        return Pressure(key, "Step Change", "SC", CAP_KIND, float("nan"))
    if key.startswith("cap"):
        # The key is the whole decimal with the point removed, so 0.02 is "cap002" and
        # 0.0005 is "cap00005". Putting the point back after the leading zero inverts
        # it; the short label then drops that zero again so it stays readable.
        digits = key.removeprefix("cap")
        intensity = float(f"{digits[0]}.{digits[1:]}")
        return Pressure(
            key, f"cap {intensity:g}", f".{digits[1:]}", CAP_KIND, intensity
        )
    if key.startswith("c") and key[1:].isdigit():
        price = float(key[1:])
        return Pressure(key, f"A${price:g}/t", f"${price:g}", PRICE_KIND, price)
    raise ValueError(f"unrecognised pressure key: {key!r}")


def order_pressures(keys: list[str]) -> list[Pressure]:
    """Pressures in presentation order: prices cheapest first, then caps shallow to deep.

    :param keys: Pressure keys in any order; duplicates collapse.
    :return: The parsed pressures, ordered.
    """
    pressures = [parse_pressure(key) for key in dict.fromkeys(keys)]
    prices = sorted(
        (p for p in pressures if p.kind == PRICE_KIND), key=lambda p: p.value
    )
    caps = sorted((p for p in pressures if p.kind == CAP_KIND), key=lambda p: -p.value)
    return prices + caps


def split_chain_id(chain_id: str) -> tuple[str, str]:
    """Split a campaign chain id into its trajectory and pressure keys.

    The pressure key is the final underscore-separated segment, because a trajectory
    key may itself contain an underscore (``low_bracket``) while a pressure key never
    does.

    :param chain_id: e.g. ``ext_low_bracket_cap0005``.
    :return: ``("low_bracket", "cap0005")``.
    """
    trajectory, _, pressure = chain_id.removeprefix(_CHAIN_PREFIX).rpartition("_")
    return trajectory, pressure


def all_demand_paths(plan: dict) -> dict[str, dict[str, float]]:
    """Base demand trajectories of the plan plus the increment grid's single-knot branches.

    The branches are read from the recorded ``increment_demand_paths_source_twh`` block and
    derived from the ``increment_grid`` block; a plan may carry either or both, and the two
    describe the same trajectories.

    :param plan: The demand plan JSON.
    :return: Source TWh keyed by financial year as a string, per trajectory.
    """
    return (
        plan["demand_paths_source_twh"]
        | plan.get(increments.INCREMENT_PATHS_KEY, {})
        | increments.demand_paths(plan)
    )


def trajectories_from_plan(plan: dict) -> list[Trajectory]:
    """Demand trajectories of the campaign, ordered smallest to largest load.

    :param plan: The demand plan JSON, keyed on ``demand_paths_source_twh``.
    :return: One trajectory per base and increment demand path, ordered by peak source load.
    """
    trajectories = [
        Trajectory(
            key=name.removeprefix(_TRAJECTORY_PREFIX),
            label=name.removeprefix(_TRAJECTORY_PREFIX).replace("_", " ").capitalize(),
            source_twh={int(year): twh for year, twh in path.items()},
        )
        for name, path in all_demand_paths(plan).items()
    ]
    return sorted(trajectories, key=lambda t: t.peak_source_twh)
