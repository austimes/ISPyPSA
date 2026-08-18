"""How well does a 13-week sample reproduce annual demand and annual VRE?

The validation solve delivered 258.455 TWh against the anchor's 251.925 TWh, a +2.59%
over-representation. Since a representative-week LP scales each sampled snapshot by
8760/(weeks*168), any sample whose mean demand differs from the annual mean carries that
error straight into absolute energy, cost and emissions.

Evaluated offline on the anchor's full-year snapshots, so no solve is needed. Reports the
committed even set, the week-51 variant, and a search over one-per-four-week-block sets
for the choice that best matches annual demand and VRE simultaneously.
"""

from datetime import datetime, timedelta
from itertools import product
from pathlib import Path

import pandas as pd
import pypsa

ANCHOR = Path(
    "analysis/benchmarks/runs_myopic/vrefix_gbc_c550_2050__cost_optimal/outputs/capacity_expansion.nc"
)
FY_START_YEAR = 2049
VRE_CARRIERS = ("Wind", "Solar")
BLOCK_SIZE = 4
N_BLOCKS = 13


def _first_monday() -> datetime:
    start = datetime(year=FY_START_YEAR, month=7, day=1)
    return start + timedelta(days=(7 - start.weekday()) % 7)


def _weekly(network: pypsa.Network) -> pd.DataFrame:
    demand = network.loads_t.p_set.sum(axis=1)
    vre = network.generators.carrier.isin(VRE_CARRIERS)
    names = network.generators.index[vre].intersection(network.generators_t.p_max_pu.columns)
    available = network.generators_t.p_max_pu[names].mul(
        network.generators.p_nom_opt[names], axis=1
    ).sum(axis=1)

    stamps = pd.DatetimeIndex(demand.index.get_level_values(-1))
    offset_days = (stamps - _first_monday()).total_seconds() / 86400
    week = pd.Series((offset_days // 7) + 1, index=demand.index)
    frame = pd.DataFrame({"demand": demand.values, "vre": available.values, "week": week.values})
    frame = frame[(frame.week >= 1) & (frame.week <= 52)]
    return frame.groupby("week")[["demand", "vre"]].mean()


def _bias(weekly: pd.DataFrame, weeks: list[int], annual: pd.Series) -> dict:
    sample = weekly.loc[weeks].mean()
    return {
        "demand_bias_pct": (sample["demand"] / annual["demand"] - 1) * 100,
        "vre_bias_pct": (sample["vre"] / annual["vre"] - 1) * 100,
    }


def main() -> None:
    network = pypsa.Network(ANCHOR)
    weekly = _weekly(network)
    # Annual mean over the 52 full weeks, the same basis a rep-week LP scales against.
    annual = weekly.mean()

    committed = [2, 6, 10, 14, 18, 22, 26, 30, 34, 38, 42, 46, 50]
    variant51 = [2, 6, 10, 14, 18, 22, 26, 30, 34, 38, 42, 46, 51]

    print("=" * 78)
    print("BIAS OF THE COMMITTED SAMPLES (vs annual mean over 52 full weeks)")
    print("=" * 78)
    for label, weeks in [("even (50)", committed), ("week-51 variant", variant51)]:
        bias = _bias(weekly, weeks, annual)
        print(f"  {label:<18} demand {bias['demand_bias_pct']:+7.3f} %   "
              f"VRE {bias['vre_bias_pct']:+7.3f} %")

    print("\n" + "=" * 78)
    print("SEARCH: one week per four-week block, minimise |demand bias| + |VRE bias|")
    print("=" * 78)
    # 4^13 is 67M combinations, so pick greedily per block (the week whose demand and
    # VRE sit closest to the annual mean) and then hill-climb on the sample mean, which
    # is what actually matters since the LP scales by the sample mean.
    blocks = [list(range(b * BLOCK_SIZE + 1, min(b * BLOCK_SIZE + BLOCK_SIZE, 52) + 1))
              for b in range(N_BLOCKS)]

    def score_of(weeks: list[int]) -> float:
        bias = _bias(weekly, weeks, annual)
        return abs(bias["demand_bias_pct"]) + abs(bias["vre_bias_pct"])

    chosen = []
    for block in blocks:
        deviations = {
            week: abs(weekly.loc[week, "demand"] / annual["demand"] - 1)
            + abs(weekly.loc[week, "vre"] / annual["vre"] - 1)
            for week in block
        }
        chosen.append(min(deviations, key=deviations.get))

    improved = True
    while improved:
        improved = False
        for index, block in enumerate(blocks):
            current = score_of(chosen)
            for candidate in block:
                if candidate == chosen[index]:
                    continue
                trial = list(chosen)
                trial[index] = candidate
                if score_of(trial) < current - 1e-9:
                    chosen, current, improved = trial, score_of(trial), True

    bias = _bias(weekly, chosen, annual)
    print(f"  greedy + hill-climb over one-per-block sets:")
    print(f"  demand {bias['demand_bias_pct']:+7.3f} %   VRE {bias['vre_bias_pct']:+7.3f} %"
          f"   score {score_of(chosen):5.3f}   {sorted(chosen)}")

    print("\n  committed even set for comparison:")
    bias = _bias(weekly, committed, annual)
    print(f"  demand {bias['demand_bias_pct']:+7.3f} %   VRE {bias['vre_bias_pct']:+7.3f} %"
          f"   score {abs(bias['demand_bias_pct']) + abs(bias['vre_bias_pct']):5.3f}   {committed}")


if __name__ == "__main__":
    main()
