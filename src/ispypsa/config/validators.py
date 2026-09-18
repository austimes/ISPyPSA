import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator

from ..templater.lists import _ISP_SCENARIOS


class PathsConfig(BaseModel):
    ispypsa_run_name: str
    parsed_traces_directory: str
    parsed_workbook_cache: str
    workbook_path: str | None
    run_directory: str

    @field_validator("parsed_traces_directory")
    @classmethod
    def validate_parsed_traces_directory(cls, parsed_traces_directory: str):
        if parsed_traces_directory == "NOT_SET_FOR_TESTING":
            return parsed_traces_directory

        if parsed_traces_directory == "ENV":
            parsed_traces_directory = os.environ.get("PATH_TO_PARSED_TRACES")
            if parsed_traces_directory is None:
                raise ValueError("Environment variable PATH_TO_PARSED_TRACES not set")

        trace_path = Path(parsed_traces_directory)
        if not trace_path.exists():
            raise NotADirectoryError(
                f"The parsed traces directory specified in the config ({parsed_traces_directory})"
                + " does not exist"
            )
        return parsed_traces_directory


class NodesConfig(BaseModel):
    regional_granularity: Literal["sub_regions", "nem_regions", "single_region"]
    rezs: Literal["discrete_nodes", "attached_to_parent_node"]


class NetworkConfig(BaseModel):
    nodes: NodesConfig
    annuitisation_lifetime: int
    transmission_expansion: bool
    rez_transmission_expansion: bool
    rez_to_sub_region_transmission_default_limit: float


class TemporalAggregationConfig(BaseModel):
    representative_weeks: list[int] | None
    named_representative_weeks: (
        list[
            Literal[
                "peak-demand",
                "residual-peak-demand",
                "minimum-demand",
                "residual-minimum-demand",
                "peak-consumption",
                "residual-peak-consumption",
            ]
        ]
        | None
    ) = None


class TemporalRangeConfig(BaseModel):
    start_year: int
    end_year: int

    @model_validator(mode="after")
    def validate_end_year(self):
        if self.end_year < self.start_year:
            raise ValueError(
                "config end_year must be greater than or equal to start_year"
            )
        return self


class TemporalDetailedConfig(BaseModel):
    reference_year_cycle: list[int]
    resolution_min: int
    aggregation: TemporalAggregationConfig

    @field_validator("resolution_min")
    @classmethod
    def validate_temporal_resolution_min(cls, operational_temporal_resolution_min: int):
        # TODO properly implement temporal aggregation so this first check can be removed.
        if operational_temporal_resolution_min != 30:
            raise ValueError(
                "config operational_temporal_resolution_min must equal 30 min"
            )
        if operational_temporal_resolution_min < 30:
            raise ValueError(
                "config operational_temporal_resolution_min must be greater than or equal to 30 min"
            )
        if (operational_temporal_resolution_min % 30) != 0:
            raise ValueError(
                "config operational_temporal_resolution_min must be multiple of 30 min"
            )
        return operational_temporal_resolution_min


class TemporalOperationalConfig(TemporalDetailedConfig):
    horizon: int
    overlap: int


class TemporalCapacityInvestmentConfig(TemporalDetailedConfig):
    investment_periods: list[int]


class TemporalConfig(BaseModel):
    year_type: Literal["fy", "calendar"]
    range: TemporalRangeConfig
    capacity_expansion: TemporalCapacityInvestmentConfig
    operational: TemporalOperationalConfig = None

    @model_validator(mode="after")
    def validate_investment_periods(self):
        if min(self.capacity_expansion.investment_periods) != self.range.start_year:
            raise ValueError(
                "config first investment period must be equal to start_year"
            )
        if len(self.capacity_expansion.investment_periods) != len(
            set(self.capacity_expansion.investment_periods)
        ):
            raise ValueError("config all years in investment_periods must be unique")
        if (
            sorted(self.capacity_expansion.investment_periods)
            != self.capacity_expansion.investment_periods
        ):
            raise ValueError(
                "config investment_periods must be provided in sequential order"
            )
        return self


class UnservedEnergyConfig(BaseModel):
    cost: float = None
    max_per_node: float = 1e5  # Default to a very large value (100,000 MW)


class TraceDataConfig(BaseModel):
    dataset_type: Literal["full", "example"] = "example"
    dataset_year: int = 2024


class CarbonPricingConfig(BaseModel):
    """Scenario-level carbon and CO2 transport-and-storage pricing.

    Both values are scalar run parameters that the carbon-price sweep varies.
    Defaults are 0.0 so omitting the section leaves existing configs unchanged.

    `tns_price` is SUPERSEDED by `ccs_supply_curve`, which prices transport per
    generator against its assigned sink and limits injection at the sink. A flat
    scalar cannot express either, because it is blind to where the CO2 has to go
    and to how much can be injected at all. It is retained so configs that set
    `tns_price` stay runnable; setting it alongside a CCS supply curve raises
    rather than double-counting disposal.
    """

    carbon_price: float = 0.0  # AUD/tCO2e on residual emissions (post-capture)
    tns_price: float = 0.0  # AUD/tCO2 on captured tonnes (superseded, see above)


class FuelPricingConfig(BaseModel):
    """How fuel carriers are priced from the IASR fuel price tables.

    AEMO blends biomethane into the gas price trajectory, so the Gas carrier's
    price rises with the mandated blend share. Setting
    `blend_biomethane_into_gas` to False prices Gas from `gas_prices` alone,
    which isolates the blend's cost effect and lets a separate bioenergy model
    carry the biomethane. Default True reproduces AEMO's own treatment.
    """

    blend_biomethane_into_gas: bool = True


class FuelSupplyCurveConfig(BaseModel):
    """Stepped supply curve for one fuel consumed by that fuel's generators.

    `curve_csv` points to a CSV defining annual price-quantity tranches
    (columns: tranche, financial_year, cap_pj, adder_$/gj). Tranche adders are
    premiums above the IASR baseline fuel prices already embedded in generator
    marginal costs, so the LP faces a convex piecewise-linear fuel cost that
    rises with total fuel consumption (ReEDS/IPM-style supply curve anchored at
    the IASR reference price). Default None leaves the fuel's supply unlimited
    at the IASR price (the pre-existing behaviour). Used for gas
    (`gas_supply_curve`) and biomass feedstock (`biomass_supply_curve`).
    """

    curve_csv: str | None = None


class CcsSupplyCurveConfig(BaseModel):
    """CO2 transport-and-storage supply curve for CO2-capturing generators.

    Two CSVs, because transport and injectivity are different quantities.
    `sink_tranches_csv` gives each CO2 storage sink's annual injection available
    to NEM power generation (columns: sink, financial_year, cap_kt, storage_$/t);
    injectivity is the shared scarce resource, so the quantity limit sits at the
    sink. `transport_csv` assigns each ISP sub-region to exactly one permitted
    sink and prices the pipeline (columns: isp_sub_region_id, sink, distance_km,
    transport_$/t); transport is a property of the source-sink pair, so it enters
    as a per-generator marginal-cost adder.

    Unlike the fuel supply curves there is no uncapped backstop tranche: a
    reservoir that has not been appraised cannot be bought at any price, so the
    curve terminates. A variant with every cap at zero is meaningful and states
    that no injection is available.

    Default None leaves CO2 disposal free and unlimited, which is the
    pre-existing behaviour and matches AEMO's own ISP treatment.
    """

    sink_tranches_csv: str | None = None
    transport_csv: str | None = None


class ModelConfig(BaseModel):
    paths: PathsConfig
    scenario: Literal[tuple(_ISP_SCENARIOS)]
    wacc: float
    discount_rate: float
    network: NetworkConfig
    temporal: TemporalConfig
    iasr_workbook_version: str
    unserved_energy: UnservedEnergyConfig
    trace_data: TraceDataConfig = TraceDataConfig()
    carbon_pricing: CarbonPricingConfig = CarbonPricingConfig()
    fuel_pricing: FuelPricingConfig = FuelPricingConfig()
    gas_supply_curve: FuelSupplyCurveConfig = FuelSupplyCurveConfig()
    biomass_supply_curve: FuelSupplyCurveConfig = FuelSupplyCurveConfig()
    ccs_supply_curve: CcsSupplyCurveConfig = CcsSupplyCurveConfig()
    filter_by_nem_regions: list[str] | None = None
    filter_by_isp_sub_regions: list[str] | None = None
    solver: Literal[
        "highs",
        "cbc",
        "glpk",
        "scip",
        "cplex",
        "gurobi",
        "xpress",
        "mosek",
        "copt",
        "mindopt",
        "pips",
    ]
    create_plots: bool = False

    @model_validator(mode="after")
    def validate_region_filters(self):
        if (
            self.filter_by_nem_regions is not None
            and self.filter_by_isp_sub_regions is not None
        ):
            raise ValueError(
                "Cannot specify both filter_by_nem_regions and filter_by_isp_sub_regions"
            )
        return self

    @model_validator(mode="after")
    def validate_ccs_supply_curve(self):
        curve = self.ccs_supply_curve
        if (curve.sink_tranches_csv is None) != (curve.transport_csv is None):
            raise ValueError(
                "ccs_supply_curve needs both sink_tranches_csv and transport_csv, "
                "or neither. Sink tranches limit injection and transport prices "
                "the pipeline to it; one without the other is a half-specified "
                "curve."
            )
        if curve.sink_tranches_csv is not None and self.carbon_pricing.tns_price != 0.0:
            raise ValueError(
                "carbon_pricing.tns_price is superseded by ccs_supply_curve and "
                "cannot be set alongside it, because both price disposal of the "
                "same captured tonne. Set tns_price to 0.0 to use the curve."
            )
        return self
