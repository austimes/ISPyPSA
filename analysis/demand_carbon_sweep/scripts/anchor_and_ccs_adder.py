"""Extract the Stage 1 anchor quantities from vrefix_gbc_c550_2050 and derive the
flat CCS transport-and-storage adder from the authored curve data.

Two jobs, one network open:

1. Anchor: generation by carrier, gas and wind energy, objective, unserved energy,
   storage build by duration class. These are the numbers Stage 1.1 must reproduce.
2. CCS adder: captured CO2 by sub-region in the solved fleet, weighted against
   analysis/ccs_market/ccs_transport_adders.csv plus the authored A$18.5/t storage
   cost, to give a single fleet-weighted A$/t.
"""

from pathlib import Path

import pandas as pd
import pypsa

RUNS = Path("analysis/benchmarks/runs_myopic")
ANCHOR = "vrefix_gbc_c550_2050"
STORAGE_COST_PER_T = 18.5  # A$/tCO2, GHD (2025) for AEMO s3.11; CCS_SUPPLY_CURVE.md s3.4


def _load(run_id):
    directory = RUNS / f"{run_id}__cost_optimal"
    network = pypsa.Network(directory / "outputs" / "capacity_expansion.nc")
    generators = pd.read_csv(directory / "pypsa_friendly" / "generators.csv")
    return network, generators, directory


def _annual_mwh(network):
    weights = network.snapshot_weightings["generators"]
    return network.generators_t.p.mul(weights, axis=0).sum()


def report_anchor(network, generators):
    print("=" * 78)
    print(f"ANCHOR: {ANCHOR}")
    print("=" * 78)
    energy = _annual_mwh(network)
    by_carrier = (energy.groupby(network.generators.carrier).sum() / 1e6).sort_values(
        ascending=False
    )
    total = by_carrier.sum()
    table = pd.DataFrame({"TWh": by_carrier, "share_%": by_carrier / total * 100})
    print(table.round(3).to_string())
    print(f"\n  total generation      {total:10.3f} TWh")
    print(f"  snapshots             {len(network.snapshots)}")
    print(f"  snapshot weight sum   {network.snapshot_weightings['generators'].sum():10.1f} h")

    gas = by_carrier.get("Gas", 0.0)
    wind = by_carrier.get("Wind", 0.0)
    print(f"\n  GAS   {gas:10.3f} TWh   {gas / total * 100:7.3f} % of generation")
    print(f"  WIND  {wind:10.3f} TWh   {wind / total * 100:7.3f} % of generation")

    use = energy[network.generators.carrier == "Unserved Energy"].sum()
    print(f"  USE   {use:10.3f} MWh")
    print(f"\n  objective             {network.objective:,.0f} AUD")
    return table, gas, wind, total


def report_storage_by_duration(network):
    print("\n" + "=" * 78)
    print("STORAGE BUILD BY DURATION CLASS")
    print("=" * 78)
    units = network.storage_units
    if units.empty:
        print("  (no storage units)")
        return
    built = units[units.p_nom_opt > 1.0].copy()
    built["duration_h"] = built["max_hours"].round(1)
    grouped = built.groupby(["carrier", "duration_h"])["p_nom_opt"].sum() / 1e3
    print(grouped.round(3).to_string())
    print(f"\n  total storage power   {built.p_nom_opt.sum() / 1e3:10.3f} GW")


def derive_ccs_adder(network, generators):
    print("\n" + "=" * 78)
    print("FLAT CCS TRANSPORT-AND-STORAGE ADDER: DERIVATION")
    print("=" * 78)
    adders = pd.read_csv("analysis/ccs_market/ccs_transport_adders.csv")
    adders["total_$/t"] = adders["transport_$/t"] + STORAGE_COST_PER_T

    intensity = generators.set_index("name")["isp_captured_co2_t_per_mwh"].fillna(0.0)
    intensity = intensity.reindex(network.generators.index).fillna(0.0)
    capturing = intensity[intensity > 0].index
    captured_t = _annual_mwh(network)[capturing] * intensity[capturing]
    by_bus = captured_t.groupby(network.generators.bus[capturing]).sum()
    by_bus = by_bus[by_bus > 0]

    table = adders.set_index("isp_sub_region_id").join(
        (by_bus / 1e6).rename("captured_Mt"), how="left"
    )
    table["captured_Mt"] = table["captured_Mt"].fillna(0.0)
    table["weight_x_price"] = table["captured_Mt"] * table["total_$/t"]
    print(
        table[["sink", "distance_km", "transport_$/t", "total_$/t", "captured_Mt", "weight_x_price"]]
        .sort_values("captured_Mt", ascending=False)
        .round(3)
        .to_string()
    )

    captured_total = table["captured_Mt"].sum()
    weighted = table["weight_x_price"].sum() / captured_total
    unweighted = table["total_$/t"].mean()
    median = table["total_$/t"].median()

    print(f"\n  total captured CO2 in anchor fleet      {captured_total:9.3f} Mt/yr")
    print(f"  FLEET-WEIGHTED adder                   {weighted:9.2f} A$/t   <-- proposed")
    print(f"  unweighted mean over 15 sub-regions    {unweighted:9.2f} A$/t")
    print(f"  median over 15 sub-regions             {median:9.2f} A$/t")
    print(f"\n  (transport per CCS_SUPPLY_CURVE.md s4.2, storage {STORAGE_COST_PER_T} A$/t per s3.4)")
    return weighted


def main():
    network, generators, _ = _load(ANCHOR)
    report_anchor(network, generators)
    report_storage_by_duration(network)
    derive_ccs_adder(network, generators)


if __name__ == "__main__":
    main()
