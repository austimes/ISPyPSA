"""Compare the Config A sampling probe against the full-year anchor.

Controlled: both solves carry the identical recursive-dynamic state (126 generators
/ 89 batteries / 54,308.63 MW / 6,198.51 MW) and the identical reducible-existing
setup. What differs is the temporal sampling (3 representative weeks at 30 min vs
the full year at 30 min) and the solver (Gurobi barrier 1e-6 vs PDLP 3e-3).

This measures what the brief's Stage 1.1 tolerance would be judging.
"""

from pathlib import Path

import pandas as pd
import pypsa

RUNS = Path("analysis/benchmarks/runs_myopic")
ANCHOR = "vrefix_gbc_c550_2050"
PROBE = "sampprobe_c550_2050"
TOLERANCE_PP = {"gas": 2.0, "wind": 2.0}


def _load(run_id):
    return pypsa.Network(RUNS / f"{run_id}__cost_optimal" / "outputs" / "capacity_expansion.nc")


def _annual_mwh(network):
    return network.generators_t.p.mul(network.snapshot_weightings["generators"], axis=0).sum()


def _mix(network):
    energy = _annual_mwh(network)
    by_carrier = energy.groupby(network.generators.carrier).sum() / 1e6
    return by_carrier[by_carrier.abs() > 1e-9].sort_values(ascending=False)


def main() -> None:
    anchor, probe = _load(ANCHOR), _load(PROBE)

    print("=" * 84)
    print("CONFIG A (3 rep weeks, 30 min) vs ANCHOR (full year, 30 min)")
    print("=" * 84)
    for label, network in [("anchor", anchor), ("probe ", probe)]:
        weights = network.snapshot_weightings["generators"]
        print(f"  {label}: {len(network.snapshots):>6} snapshots, "
              f"weight sum {weights.sum():>8.1f} h")

    anchor_mix, probe_mix = _mix(anchor), _mix(probe)
    table = pd.DataFrame({"anchor_TWh": anchor_mix, "probe_TWh": probe_mix}).fillna(0.0)
    table["anchor_%"] = table["anchor_TWh"] / table["anchor_TWh"].sum() * 100
    table["probe_%"] = table["probe_TWh"] / table["probe_TWh"].sum() * 100
    table["delta_pp"] = table["probe_%"] - table["anchor_%"]
    print("\n" + table.round(3).to_string())

    print("\n" + "-" * 84)
    print("STAGE 1.1 TOLERANCE CHECK (brief: gas and wind within 2%)")
    print("-" * 84)
    for carrier, key in [("Gas", "gas"), ("Wind", "wind")]:
        a = table.loc[carrier, "anchor_TWh"]
        p = table.loc[carrier, "probe_TWh"]
        rel = (p - a) / a * 100
        pp = table.loc[carrier, "delta_pp"]
        verdict = "PASS" if abs(rel) <= TOLERANCE_PP[key] else "FAIL"
        print(f"  {carrier:<6} anchor {a:8.3f} TWh   probe {p:8.3f} TWh   "
              f"rel {rel:+8.2f} %   share {pp:+6.2f} pp   -> {verdict}")

    use_a = _annual_mwh(anchor)[anchor.generators.carrier == "Unserved Energy"].sum()
    use_p = _annual_mwh(probe)[probe.generators.carrier == "Unserved Energy"].sum()
    print(f"\n  unserved energy   anchor {use_a:10.3f} MWh   probe {use_p:10.3f} MWh")

    print("\n" + "-" * 84)
    print("STORAGE BUILD BY DURATION CLASS (GW), and the sub-4h share")
    print("-" * 84)
    for label, network in [("anchor", anchor), ("probe", probe)]:
        units = network.storage_units
        built = units[units.p_nom_opt > 1.0]
        batteries = built[built.carrier == "Battery"]
        sub4 = batteries[batteries.max_hours < 4.0]["p_nom_opt"].sum() / 1e3
        total_bat = batteries["p_nom_opt"].sum() / 1e3
        phes = built[built.carrier == "Water"]["p_nom_opt"].sum() / 1e3
        print(f"  {label:<7} battery {total_bat:7.3f} GW  of which <4h {sub4:6.3f} GW"
              f"  ({sub4 / total_bat * 100 if total_bat else 0:5.1f} %)   PHES {phes:7.3f} GW")


if __name__ == "__main__":
    main()
