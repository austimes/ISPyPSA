"""Derive the sweep's demand scalars from AEMO's own 2026 ISP Final demand traces.

Basis, held identical across the three scenarios so the ratio is a pure scenario
effect: POE50, OPSO_MODELLING (grid-served operational demand, the demand_type
the parsed store carries), reference year 2018, all 15 ISP sub-regions, summed to
a NEM total per financial year.

Prints FY2030 / FY2040 / FY2050 NEM energy per scenario and the 2050 ratios.
"""

from pathlib import Path

import pandas as pd

RAW = Path("iasr inputs/2026 ISP Final")
SUBREGIONS = [
    "CNSW", "CQ", "CSA", "GG", "MEL", "NNSW", "NQ", "NSA",
    "SESA", "SEV", "SNSW", "SNW", "SQ", "TAS", "WNV",
]
SCENARIOS = {
    "Step Change": "STEP_CHANGE",
    "Slower Growth": "SLOWER_GROWTH",
    "Accelerated Transition": "ACCELERATED_TRANSITION",
}
REF_YEAR = 2018
HALF_HOUR_COLS = [f"{i:02d}" for i in range(1, 49)]


def _trace_path(subregion: str, scenario: str, tag: str) -> Path:
    folder = RAW / f"ISP Demand Traces {subregion} {scenario}" / f"demand_{subregion}_{scenario}"
    matches = list(folder.glob(f"*_{subregion}_RefYear_{REF_YEAR}_{tag}_POE50_OPSO_MODELLING.csv"))
    assert len(matches) == 1, f"{subregion}/{scenario}: {len(matches)} matches"
    return matches[0]


def _financial_year_energy_twh(path: Path) -> pd.Series:
    """Sum a raw AEMO half-hourly demand CSV to TWh per financial year."""
    df = pd.read_csv(path)
    # FY2050 == Jul 2049 -> Jun 2050, so months after June belong to the next FY.
    fy = df["Year"] + (df["Month"] > 6).astype(int)
    mwh = df[HALF_HOUR_COLS].sum(axis=1) * 0.5  # 48 half-hour MW readings -> MWh
    return mwh.groupby(fy).sum() / 1e6


def main() -> None:
    totals = {}
    for scenario, tag in SCENARIOS.items():
        per_subregion = [
            _financial_year_energy_twh(_trace_path(sr, scenario, tag)) for sr in SUBREGIONS
        ]
        totals[scenario] = pd.concat(per_subregion, axis=1).sum(axis=1)

    table = pd.DataFrame(totals)
    print("NEM demand energy, TWh (POE50, OPSO_MODELLING, RefYear 2018, 15 sub-regions)")
    print(table.loc[[2030, 2040, 2050]].round(3).to_string())

    print("\n2050 ratios vs Step Change:")
    base = table.loc[2050, "Step Change"]
    for scenario in SCENARIOS:
        value = table.loc[2050, scenario]
        print(f"  {scenario:<24} {value:8.3f} TWh   ratio {value / base:.6f}")

    print("\nFull FY series (TWh):")
    print(table.round(3).to_string())


if __name__ == "__main__":
    main()
