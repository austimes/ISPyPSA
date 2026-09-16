"""Forward-basis 2025 anchor for the ShARP electricity histories.

Fixes the 2025-to-2030 cost discontinuity at its source: the candidate
histories currently copy ShARP's provisional A$54.99/MWh 2025 row (a mixed
cost basis) and then drop to the forward-basis 2030 value. This export gives
every history a 2025 row on the SAME avoidable-cost basis as 2030+: the 2025
fleet is almost entirely inherited, so its forward conversion cost is
retention fixed O&M plus variable O&M, with no capacity-expansion solve.

Pure data ledger from the committed IASR-templated ECAA table (identical
across runs; read from one B run's ispypsa_inputs). 2025 fleet = units with
commissioning on or before FY2025 end and closure year after 2025.

Exports A$/yr and per-carrier components, NOT a blended A$/MWh: the activity
denominator (observed 2025 residual-grid TWh) and the dispatch mix used to
weight VOM are ShARP-side observed quantities, so the coefficient is formed
there. Fuel and carbon are excluded by the conversion-cost convention.
Committed builds commissioning in FY2025 are listed separately so the
electricity author can rule on whether base-year-committed capital is charged
(the avoidable-cost convention normally does not charge decisions already
taken).

Usage:
    uv run python analysis/intensity_demand_map/scripts/export_2025_anchor.py
"""

from pathlib import Path

import pandas as pd

INPUTS = Path(
    "analysis/benchmarks/runs_myopic/sweep_c0_d100_2030__cost_optimal/ispypsa_inputs"
)
ECAA = INPUTS / "ecaa_generators.csv"
ECAA_STORAGE = INPUTS / "ecaa_batteries.csv"
OUT = Path("analysis/intensity_demand_map")
ANCHOR_FY = 2025


def main() -> None:
    ecaa = pd.read_csv(ECAA)
    commissioning_year = pd.to_datetime(
        ecaa["commissioning_date"], errors="coerce"
    ).dt.year
    # FY2025 ends 2025-06-30: anything commissioning by then is in the anchor
    # fleet; NaT commissioning = long-existing plant, included.
    in_2025 = (commissioning_year.fillna(1900) <= ANCHOR_FY) & (
        ecaa["closure_year"].fillna(9999) > ANCHOR_FY
    )
    fleet = ecaa[in_2025].copy()
    fleet["fom_aud_per_yr"] = (
        fleet["fom_$/kw/annum"].fillna(0.0) * fleet["maximum_capacity_mw"] * 1000.0
    )

    by_carrier = (
        fleet.groupby("fuel_type")
        .agg(
            units=("generator", "count"),
            installed_mw=("maximum_capacity_mw", "sum"),
            fom_aud_per_yr=("fom_aud_per_yr", "sum"),
            vom_aud_per_mwh_capacity_weighted=(
                "vom_$/mwh_sent_out",
                lambda s: (
                    (s.fillna(0.0) * fleet.loc[s.index, "maximum_capacity_mw"]).sum()
                    / fleet.loc[s.index, "maximum_capacity_mw"].sum()
                ),
            ),
        )
        .reset_index()
    )
    by_carrier.to_csv(OUT / "anchor_2025_forward_components.csv", index=False)

    committed_fy2025 = ecaa[
        (commissioning_year == ANCHOR_FY) & (ecaa["closure_year"].fillna(9999) > ANCHOR_FY)
    ][["generator", "fuel_type", "maximum_capacity_mw", "status", "commissioning_date"]]
    committed_fy2025.to_csv(OUT / "anchor_2025_committed_fy2025.csv", index=False)

    storage = pd.read_csv(ECAA_STORAGE)
    storage_commissioning = pd.to_datetime(
        storage["commissioning_date"], errors="coerce"
    ).dt.year
    storage_2025 = storage[
        (storage_commissioning.fillna(1900) <= ANCHOR_FY)
        & (storage["closure_year"].fillna(9999) > ANCHOR_FY)
    ].copy()
    storage_2025["fom_aud_per_yr"] = (
        storage_2025["fom_$/kw/annum"].fillna(0.0)
        * storage_2025["maximum_capacity_mw"]
        * 1000.0
    )
    storage_summary = (
        storage_2025.groupby("fuel_type")
        .agg(units=("storage_name", "count"),
             installed_mw=("maximum_capacity_mw", "sum"),
             fom_aud_per_yr=("fom_aud_per_yr", "sum"))
        .reset_index()
    )
    storage_summary["fuel_type"] = "Storage: " + storage_summary["fuel_type"]
    storage_summary.to_csv(
        OUT / "anchor_2025_forward_components_storage.csv", index=False
    )

    print(by_carrier.round(2).to_string(index=False))
    print(storage_summary.round(2).to_string(index=False))
    total_fom = fleet["fom_aud_per_yr"].sum() + storage_2025["fom_aud_per_yr"].sum()
    print(f"\ntotal 2025 fleet: {fleet['maximum_capacity_mw'].sum():,.0f} MW gen + "
          f"{storage_2025['maximum_capacity_mw'].sum():,.0f} MW storage, "
          f"FOM {total_fom / 1e9:.3f} A$bn/yr")
    print(f"FY2025-commissioning units listed separately: {len(committed_fy2025)}")
    print("wrote anchor_2025_forward_components{,_storage}.csv, "
          "anchor_2025_committed_fy2025.csv")


if __name__ == "__main__":
    main()
