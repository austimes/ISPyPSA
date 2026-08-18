"""Select the thirteen representative weeks for the sweep's Config B, with evidence.

Stress is measured on the anchor network (vrefix_gbc_c550_2050): a full-year
30-minute post-repair solve, so its snapshots carry the real FY2050 demand and the
real reference-year-2018 VRE availability against the real solved fleet.

Metric: residual demand = demand - available VRE, where available VRE is
p_max_pu * p_nom_opt summed over Wind and Solar. Weeks are indexed the way
ISPyPSA indexes them (temporal_filters.py:226-229): week 1 starts on the first
Monday on or after 1 July of the financial year's start year, week N starts
7*(N-1) days later.

Selection rule: one week per four-week block across the 52-week year, then the
block containing the worst residual week is represented by that week rather than
by its block default.
"""

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pypsa

ANCHOR = Path(
    "analysis/benchmarks/runs_myopic/vrefix_gbc_c550_2050__cost_optimal/outputs/capacity_expansion.nc"
)
FY_START_YEAR = 2049  # FY2050 spans 2049-07-01 -> 2050-06-30
VRE_CARRIERS = ("Wind", "Solar")
BLOCK_SIZE = 4
N_WEEKS = 13


def _first_monday() -> datetime:
    start = datetime(year=FY_START_YEAR, month=7, day=1)
    return start + timedelta(days=(7 - start.weekday()) % 7)


def _week_index(timestamps: pd.DatetimeIndex) -> pd.Series:
    """ISPyPSA week number for each snapshot; NaN outside the 52 full weeks."""
    offset_days = (timestamps - _first_monday()).total_seconds() / 86400
    week = (offset_days // 7) + 1
    week = pd.Series(week, index=timestamps)
    return week.where((week >= 1) & (week <= 52))


def _residual_by_week(network: pypsa.Network) -> pd.DataFrame:
    demand = network.loads_t.p_set.sum(axis=1)
    vre = network.generators.carrier.isin(VRE_CARRIERS)
    vre_names = network.generators.index[vre].intersection(network.generators_t.p_max_pu.columns)
    available = network.generators_t.p_max_pu[vre_names].mul(
        network.generators.p_nom_opt[vre_names], axis=1
    ).sum(axis=1)

    frame = pd.DataFrame({"demand_mw": demand, "vre_mw": available})
    frame["residual_mw"] = frame["demand_mw"] - frame["vre_mw"]
    frame["vre_ratio"] = frame["vre_mw"] / frame["demand_mw"]
    # multi_investment_periods=True gives a (period, timestep) MultiIndex; the
    # timestep level carries the datetime.
    timestamps = pd.DatetimeIndex(frame.index.get_level_values(-1))
    frame["week"] = _week_index(timestamps).values

    weekly = frame.dropna(subset=["week"]).groupby("week").agg(
        demand_gwh=("demand_mw", lambda s: s.sum() * 0.5 / 1e3),
        vre_gwh=("vre_mw", lambda s: s.sum() * 0.5 / 1e3),
        residual_gwh=("residual_mw", lambda s: s.sum() * 0.5 / 1e3),
        mean_vre_ratio=("vre_ratio", "mean"),
        peak_residual_mw=("residual_mw", "max"),
    )
    weekly.index = weekly.index.astype(int)
    return weekly


def _select(weekly: pd.DataFrame) -> tuple[list[int], int]:
    """One week per four-week block; the worst-residual block yields its worst week."""
    worst = int(weekly["residual_gwh"].idxmax())
    worst_block = (worst - 1) // BLOCK_SIZE

    selected = []
    for block in range(N_WEEKS):
        if block == worst_block:
            selected.append(worst)
            continue
        # Block default: the block's middle week, keeping the spread even.
        selected.append(block * BLOCK_SIZE + 2)
    return sorted(set(selected)), worst


def main() -> None:
    network = pypsa.Network(ANCHOR)
    weekly = _residual_by_week(network)

    print("=" * 92)
    print("WEEKLY RESIDUAL DEMAND, FY2050, reference year 2018, anchor solved fleet")
    print("=" * 92)
    ranked = weekly.sort_values("residual_gwh", ascending=False)
    print("\nTen most VRE-stressed weeks (highest residual energy):")
    print(ranked.head(10).round(3).to_string())
    print("\nTen least-stressed weeks:")
    print(ranked.tail(10).round(3).to_string())

    selected, worst = _select(weekly)
    print("\n" + "=" * 92)
    print("SELECTION")
    print("=" * 92)
    print(f"  worst residual week: {worst}  "
          f"(week starts {_first_monday() + timedelta(weeks=worst - 1):%Y-%m-%d})")
    print(f"  selected weeks ({len(selected)}): {selected}")
    print("\nSelected weeks' metrics:")
    print(weekly.loc[selected].round(3).to_string())

    print("\n  residual-energy percentile of each selected week "
          "(100 = most stressed of 52):")
    pct = weekly["residual_gwh"].rank(pct=True) * 100
    for week in selected:
        print(f"    week {week:>2}  {pct.loc[week]:6.1f}")


if __name__ == "__main__":
    main()
