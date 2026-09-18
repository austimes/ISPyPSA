"""Extend a fuel supply curve CSV to later investment periods by holding its last year.

The gas and biomass supply curves (tranche, financial_year, cap_pj, adder_$/gj) end at
FY2055, but the extension campaign solves a 2060 milestone. The campaign brief holds every
trajectory-valued input at its last published year beyond the data, so the held copy
repeats the final year's tranche rows for each requested later year. The output is an
authored extension and should be written under the run's output directory.

Usage:
    uv run python analysis/benchmarks/hold_supply_curves.py \\
        --curve analysis/gas_market/gas_supply_curve_central.csv \\
        --out outputs/inputs/gas_supply_curve_held_to_2060.csv \\
        --years 2060
"""

import argparse
import logging
from pathlib import Path

import pandas as pd


def hold_curve_to_years(curve: pd.DataFrame, years: list[int]) -> pd.DataFrame:
    """Append the last published year's rows relabelled to each missing later year.

    Years already present in the curve are left untouched, so the held copy is
    identical to the source over the published span.
    """
    last_year = int(curve["financial_year"].max())
    missing = sorted(year for year in years if year > last_year)
    held_rows = [
        curve[curve["financial_year"] == last_year].assign(financial_year=year)
        for year in missing
    ]
    if missing:
        logging.warning(
            f"Supply curve held at FY{last_year} for investment periods beyond the "
            f"published data: {missing}"
        )
    return pd.concat([curve, *held_rows], ignore_index=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--curve", type=Path, required=True, help="Source curve CSV")
    parser.add_argument("--out", type=Path, required=True, help="Held copy to write")
    parser.add_argument(
        "--years", type=int, nargs="+", required=True, help="Years the copy must cover"
    )
    args = parser.parse_args()

    held = hold_curve_to_years(pd.read_csv(args.curve), args.years)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    held.to_csv(args.out, index=False, lineterminator="\n")
    print(f"wrote {args.out} ({len(held)} rows, to FY{held['financial_year'].max()})")


if __name__ == "__main__":
    main()
