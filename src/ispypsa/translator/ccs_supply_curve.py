import logging

import pandas as pd

_SINK_TRANCHE_COLUMNS = ["sink", "financial_year", "cap_kt", "storage_$/t"]
_TRANSPORT_COLUMNS = ["isp_sub_region_id", "sink", "distance_km", "transport_$/t"]


def _translate_ccs_sink_tranches(
    sink_tranches_csv: str, investment_periods: list[int]
) -> pd.DataFrame:
    """Filters the CO2 sink injectivity tranche CSV to the modelled investment periods.

    The CSV defines, per CO2 storage sink per year, how much CO2 can be injected
    and what storage costs there. Columns are 'sink' (str label matching the
    'sink' column of the transport adder CSV), 'financial_year' (int, financial
    year ending, matching investment period labels), 'cap_kt' (float, kt CO2 per
    year available to NEM power generation) and 'storage_$/t' (float, real AUD
    per tonne injected).

    Unlike the fuel supply curves there is no uncapped backstop tranche: a sink
    that has not been appraised cannot be bought at any price, so the curve
    terminates. A variant in which every `cap_kt` is zero is therefore a valid
    and meaningful curve — it states that no injection is available — and forces
    captured tonnes to zero.

    Args:
        sink_tranches_csv: path to the sink tranche definition CSV.
        investment_periods: list of years in which investment periods start.

    Returns: `pd.DataFrame` with columns 'investment_period', 'sink', 'cap_kt'
        and 'storage_$/t', one row per sink per investment period.
    """
    logging.info("Creating CCS CO2 sink tranche inputs")
    tranches = pd.read_csv(sink_tranches_csv)
    _validate_columns(tranches, _SINK_TRANCHE_COLUMNS, sink_tranches_csv)
    tranches = tranches[tranches["financial_year"].isin(investment_periods)]
    tranches = tranches.rename(columns={"financial_year": "investment_period"})
    _validate_period_coverage(tranches, investment_periods, sink_tranches_csv)
    columns = ["investment_period", "sink", "cap_kt", "storage_$/t"]
    return tranches[columns].reset_index(drop=True)


def _translate_ccs_transport_adders(transport_csv: str) -> pd.DataFrame:
    """Reads the per-sub-region CO2 transport adder and sink assignment CSV.

    Each ISP sub-region is assigned exactly one permitted sink and the per-tonne
    cost of piping CO2 there. Columns are 'isp_sub_region_id', 'sink',
    'distance_km' and 'transport_$/t' (real AUD per tonne captured).

    Args:
        transport_csv: path to the transport adder definition CSV.

    Returns: `pd.DataFrame` with columns 'isp_sub_region_id', 'sink' and
        'transport_$/t'.
    """
    logging.info("Creating CCS CO2 transport adder inputs")
    adders = pd.read_csv(transport_csv)
    _validate_columns(adders, _TRANSPORT_COLUMNS, transport_csv)
    _validate_unique_sub_regions(adders, transport_csv)
    return adders[["isp_sub_region_id", "sink", "transport_$/t"]]


def _map_generators_to_sinks(
    generators: pd.DataFrame, transport_adders: pd.DataFrame
) -> pd.Series:
    """The assigned CO2 sink of each generator that captures CO2, keyed by name.

    Derived from the generator's bus at the point of use rather than read from a
    stored column, because carried recursive-dynamic tranche rows are appended to
    the generators table after translation and are aligned to whatever columns
    existed when they were written. A stored sink column would be NaN on every
    carried row, and `groupby` drops NaN groups silently, which would leave the
    entire inherited CCS fleet outside the injectivity constraint.

    Args:
        generators: `PyPSA` formatted generators table.
        transport_adders: output of `_translate_ccs_transport_adders`.

    Returns: `pd.Series` of sink labels indexed by generator name, covering only
        generators with a non-zero captured intensity.
    """
    capturing = generators[_captures_co2(generators)]
    _validate_capturing_buses_are_assigned(capturing["bus"], transport_adders)
    sinks = transport_adders.set_index("isp_sub_region_id")["sink"]
    return capturing.set_index("name")["bus"].map(sinks)


def _add_ccs_transport_columns(
    generators: pd.DataFrame, transport_adders: pd.DataFrame
) -> pd.DataFrame:
    """Attaches `isp_ccs_transport_$/t` to the generators table.

    Keyed on the generator's bus, which is the ISP sub-region id at
    `sub_regions` regional granularity. Only generators that capture CO2 carry an
    adder; everything else gets 0.0, so the marginal-cost calculation is a no-op
    for them. Idempotent, so it can be re-applied after carried tranche rows are
    appended to pick up the rows that were aligned in without it.

    Args:
        generators: `PyPSA` formatted generators table.
        transport_adders: output of `_translate_ccs_transport_adders`.

    Returns: the generators table with the transport adder column added.
    """
    g = generators.copy()
    captures = _captures_co2(g)
    _validate_capturing_buses_are_assigned(g.loc[captures, "bus"], transport_adders)
    costs = transport_adders.set_index("isp_sub_region_id")["transport_$/t"]
    g["isp_ccs_transport_$/t"] = g["bus"].map(costs).where(captures).fillna(0.0)
    return g


def _captures_co2(generators: pd.DataFrame) -> pd.Series:
    """Boolean mask of generators with a non-zero captured CO2 intensity."""
    return (
        pd.to_numeric(
            generators["isp_captured_co2_t_per_mwh"], errors="coerce"
        ).fillna(0.0)
        > 0
    )


def _validate_sinks_have_tranches(
    transport_adders: pd.DataFrame, sink_tranches: pd.DataFrame
) -> None:
    """Every assigned sink must have tranche rows, or its tonnes go unconstrained."""
    assigned = set(transport_adders["sink"])
    tranched = set(sink_tranches["sink"])
    missing = sorted(assigned - tranched)
    if missing:
        raise ValueError(
            f"CCS transport adders assign sub-regions to sinks that have no "
            f"injectivity tranche rows, so their captured CO2 would be "
            f"unconstrained: {missing}"
        )


def _validate_columns(table: pd.DataFrame, expected: list[str], csv: str) -> None:
    missing = [c for c in expected if c not in table.columns]
    if missing:
        raise ValueError(f"CCS supply curve CSV ({csv}) is missing columns: {missing}")


def _validate_period_coverage(
    tranches: pd.DataFrame, investment_periods: list[int], csv: str
) -> None:
    covered = set(tranches["investment_period"])
    missing = [year for year in investment_periods if year not in covered]
    if missing:
        raise ValueError(
            f"CCS sink tranche CSV ({csv}) has no rows for investment periods: "
            f"{sorted(missing)}"
        )


def _validate_unique_sub_regions(adders: pd.DataFrame, csv: str) -> None:
    duplicated = sorted(
        adders.loc[adders["isp_sub_region_id"].duplicated(), "isp_sub_region_id"]
    )
    if duplicated:
        raise ValueError(
            f"CCS transport adder CSV ({csv}) assigns more than one sink to "
            f"sub-regions: {duplicated}. Each sub-region takes exactly one sink."
        )


def _validate_capturing_buses_are_assigned(
    capturing_buses: pd.Series, transport_adders: pd.DataFrame
) -> None:
    assigned = set(transport_adders["isp_sub_region_id"])
    unassigned = sorted(set(capturing_buses) - assigned)
    if unassigned:
        raise ValueError(
            f"Generators that capture CO2 sit at buses with no CO2 sink "
            f"assignment, so their disposal cannot be priced: {unassigned}. The "
            f"CCS supply curve requires `sub_regions` regional granularity and a "
            f"transport adder row per sub-region."
        )
