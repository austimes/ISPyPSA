"""Week-51 sensitivity, and whether the stalled Sub-optimal solutions agree.

Three sampled solves plus the full-year anchor. All three sampled solves stalled
Sub-optimal with no objective, so the question for the pause is whether their
generation mixes nonetheless agree: if they do, mix-based deliverables survive the
solver failure even though cost-based ones do not.
"""

from pathlib import Path

import pandas as pd
import pypsa

RUNS = Path("analysis/benchmarks/runs_myopic")
CELLS = {
    "anchor": "vrefix_gbc_c550_2050",
    "even50_1e6": "val13_c550_2050",
    "even50_1e8": "val13x_c550_2050",
    "wk51_1e6": "val13s51_c550_2050",
}


def _mix(run_id):
    network = pypsa.Network(RUNS / f"{run_id}__cost_optimal" / "outputs" / "capacity_expansion.nc")
    energy = network.generators_t.p.mul(network.snapshot_weightings["generators"], axis=0).sum()
    by_carrier = energy.groupby(network.generators.carrier).sum() / 1e6
    by_carrier = by_carrier[by_carrier.abs() > 1e-9]
    use = float(energy[network.generators.carrier == "Unserved Energy"].sum())
    return by_carrier, use


def main():
    shares, twh, uses = {}, {}, {}
    for label, run_id in CELLS.items():
        by_carrier, use = _mix(run_id)
        twh[label] = by_carrier
        shares[label] = by_carrier / by_carrier.sum() * 100
        uses[label] = use

    share_table = pd.DataFrame(shares).fillna(0.0)
    print("=" * 88)
    print("GENERATION SHARE (% of generation)")
    print("=" * 88)
    print(share_table.round(3).to_string())

    print("\n" + "-" * 88)
    print("DELTA vs ANCHOR (percentage points)")
    print("-" * 88)
    deltas = share_table.drop(columns="anchor").sub(share_table["anchor"], axis=0)
    print(deltas.round(3).to_string())

    print("\n" + "-" * 88)
    print("WEEK-51 SENSITIVITY (report only, not a gate)")
    print("-" * 88)
    gas_50 = share_table.loc["Gas", "even50_1e6"]
    gas_51 = share_table.loc["Gas", "wk51_1e6"]
    print(f"  gas share, week 50 in slot   {gas_50:7.3f} %")
    print(f"  gas share, week 51 in slot   {gas_51:7.3f} %")
    print(f"  movement                     {gas_51 - gas_50:+7.3f} pp")
    print(f"  anchor                       {share_table.loc['Gas', 'anchor']:7.3f} %")

    print("\n" + "-" * 88)
    print("DO THE STALLED SOLUTIONS AGREE? (max spread across the 3 sampled solves)")
    print("-" * 88)
    sampled = share_table[["even50_1e6", "even50_1e8", "wk51_1e6"]]
    spread = (sampled.max(axis=1) - sampled.min(axis=1)).sort_values(ascending=False)
    print(spread.round(3).to_string())
    print(f"\n  largest spread {spread.max():.3f} pp")

    print("\n  unserved energy (MWh):")
    for label, use in uses.items():
        print(f"    {label:<14} {use:10.3f}")


if __name__ == "__main__":
    main()
