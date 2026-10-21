import pandas as pd

from .helpers import _snakecase_string
from .lists import (
    _ALL_GENERATOR_STORAGE_TYPES,
    _CONDENSED_GENERATOR_TYPES,
    _ECAA_BATTERY_TYPES,
    _ECAA_GENERATOR_TYPES,
    _ISP_SCENARIOS,
)

_NEM_REGION_IDS = pd.Series(
    {
        "Queensland": "QLD",
        "New South Wales": "NSW",
        "Victoria": "VIC",
        "South Australia": "SA",
        "Tasmania": "TAS",
    },
    name="nem_region_id_mapping",
)

_SINGLE_REGION_ID = "NEM"

_NEM_SUB_REGION_IDS = pd.Series(
    {
        "Northern Queensland": "NQ",
        "Central Queensland": "CQ",
        "Gladstone Grid": "GG",
        "Southern Queensland": "SQ",
        "Northern New South Wales": "NNSW",
        "Central New South Wales": "CNSW",
        "Southern New South Wales": "SNSW",
        "Sydney, Newcastle, Wollongong": "SNW",
        # v7.4 split the single "Victoria" subregion into three (MEL/SEV/WNV) and
        # added "Northern South Australia". "Victoria" is kept for the regional
        # reference-node table (the VIC region). Without the three VIC + NSA
        # entries, these fall through as descriptive names (or fuzzy-match the
        # stale "Victoria"->VIC) and no longer match the demand store's codes.
        "Victoria": "VIC",
        "Greater Melbourne and Geelong": "MEL",
        "South East Victoria": "SEV",
        "West and North Victoria": "WNV",
        "Central South Australia": "CSA",
        "Northern South Australia": "NSA",
        "South East South Australia": "SESA",
        "Tasmania": "TAS",
    },
    name="nem_region_id_mapping",
)

_HVDC_FLOW_PATHS = pd.DataFrame(
    {
        "node_from": ["NNSW", "VIC", "TAS"],
        "node_to": ["SQ", "CSA", "VIC"],
        "flow_path": ["Terranora", "Murraylink", "Basslink"],
    }
)

_GENERATOR_PROPERTIES = {
    "maximum_capacity": _ALL_GENERATOR_STORAGE_TYPES,
    "seasonal_ratings": _ALL_GENERATOR_STORAGE_TYPES,
    "maintenance": ["existing_generators", "new_entrants"],
    "fixed_opex": _CONDENSED_GENERATOR_TYPES,
    "variable_opex": _CONDENSED_GENERATOR_TYPES,
    "marginal_loss_factors": _ALL_GENERATOR_STORAGE_TYPES,
    "auxiliary_load": _CONDENSED_GENERATOR_TYPES,
    "heat_rates": _CONDENSED_GENERATOR_TYPES,
    "outages_2023-2024": ["existing_generators"],
    "long_duration_outages": ["existing_generators"],
    "outages": ["new_entrants"],
    "full_outages_forecast": ["existing_generators"],
    "partial_outages_forecast": ["existing_generators"],
    "gpg_min_stable_level": ["existing_generators", "new_entrants"],
    "coal_prices": list(map(_snakecase_string, _ISP_SCENARIOS)),
    "gas_prices": list(map(_snakecase_string, _ISP_SCENARIOS)),
}

_ECAA_GENERATOR_NEW_COLUMN_MAPPING = {
    "partial_outage_derating_factor_%": "forced_outage_rate_partial_outage_%_of_time",
    "commissioning_date": "generator",
    "closure_year": "generator",
    # Auxiliary load is published per generator and looked up by Power Station, so
    # seed the summary's `auxiliary_load_%` column with the generator name.
    "auxiliary_load_%": "generator",
    # The summary's own `FOM ($/kW/annum)` cell is a lookup key, not a value, and
    # AEMO only writes a station name there for thermal plant. Wind, solar and
    # hydro rows carry a class label ("All Wind", "All Large scale solar PV",
    # "All Hydro") and two gas rows carry a technology label ("OCGT (small GT)").
    # `fixed_opex_existing_committed_anticipated_additional_generators` is keyed
    # solely by Power Station and has no such rows, so the lookup missed and
    # `_merge_and_set_ecaa_generators_static_properties` turned the leftover
    # string into pd.NA on 274 of 336 rows. There is no class-level FOM anywhere
    # in the workbook to reach instead (the Fixed OPEX sheet is 737 per-station
    # rows, none of them an "All ..." aggregate), so the class labels are AEMO
    # shorthand for "these are listed individually" and the per-station join is
    # the intended mapping. Seed from the generator name like the other
    # Power-Station-keyed lookups above; thermal is unaffected because its
    # summary cell already held that same station name.
    "fom_$/kw/annum": "generator",
}

_NEW_ENTRANT_GENERATOR_NEW_COLUMN_MAPPING = {
    "partial_outage_derating_factor_%": "forced_outage_rate_partial_outage_%_of_time",
    # "maximum_capacity_mw": "generator_name",
    # "unit_capacity_mw": "generator_name",
    "lifetime": "generator_name",
    "minimum_stable_level_%": "technology_type",
    # new_entrants_summary has no per-row Summer/Winter rating columns. The
    # static-property lookup against seasonal_ratings_new_entrants uses these
    # columns as the fuzzy-match key, so `technology_type` seeds all three.
    "summer_peak_rating_%": "technology_type",
    "summer_rating_mw": "technology_type",
    "winter_rating_mw": "technology_type",
    "technology_specific_lcf_%": "regional_build_cost_zone",
}

_ECAA_STORAGE_NEW_COLUMN_MAPPING = {
    "maximum_capacity_mw": "storage_name",
    "energy_capacity_mwh": "storage_name",
    "storage_duration_hours": "storage_name",
    "round_trip_efficiency_%": "fom_$/kw/annum",
    "charging_efficiency_%": "fom_$/kw/annum",
    "discharging_efficiency_%": "fom_$/kw/annum",
    "lifetime": "storage_name",
    "commissioning_date": "storage_name",
    "closure_year": "storage_name",
    "isp_resource_type": "fom_$/kw/annum",
}

_NEW_STORAGE_NEW_COLUMN_MAPPING = {
    # v7.5 renamed new-entrant batteries from the generic tech label to
    # per-subregion names ("NQ Battery - 1h"), so the static-property columns
    # must be seeded from `technology_type` (the generic "Battery Storage
    # (Nhr storage)") — which is what the property tables are keyed on — rather
    # than `storage_name`. In v7.4 the two were identical, so no regression.
    "maximum_capacity_mw": "technology_type",
    "storage_duration_hours": "technology_type",
    "round_trip_efficiency_%": "technology_type",
    "charging_efficiency_%": "technology_type",
    "discharging_efficiency_%": "technology_type",
    "lifetime": "technology_type",
    "technology_specific_lcf_%": "regional_build_cost_zone",
    "isp_resource_type": "technology_type",
}

"""
_NEW_COLUMN_MAPPING dicts define new/additional columns to be added to the corresponding
ECAA or new entrant generator summary tables. Keys are the name of the column to be added
(corresponding to the table/column name of the data being added) and values are the name
of the column in the existing summary table that holds the required data mapping for merging
in the new column.
"""

_ECAA_GENERATOR_STATIC_PROPERTY_TABLE_MAP = {
    "maximum_capacity_mw": dict(
        table="maximum_capacity_existing_committed_anticipated_additional_generators",
        table_lookup="Power Station",
        table_value="Installed capacity (MW)",
    ),
    "commissioning_date": dict(
        table="maximum_capacity_existing_committed_anticipated_additional_generators",
        table_lookup="Power Station",
        table_value="Commissioning date",
        # Confirmed (Committed) dates land in `Commissioning date`; indicative
        # (Anticipated/Additional) dates land in `Indicative commissioning date`.
        # Schema normalisation splits the workbook's single date column by Status.
        alternative_values=["Indicative commissioning date"],
    ),
    "maintenance_duration_%": dict(
        table="maintenance_existing_generators",
        table_lookup="Generator type",
        table_value="Proportion of time out (%)",
    ),
    "minimum_load_mw": dict(
        table="coal_minimum_stable_level",
        # Keyed by per-unit IASR ID; the value is the technical floor sub-column.
        table_lookup="IASR ID",
        table_value="Minimum Stable Level (MW)_Minimum Continuous Operating Level",
    ),
    "fom_$/kw/annum": dict(
        table="fixed_opex_existing_committed_anticipated_additional_generators",
        table_lookup="Power Station",
        table_value="Fixed OPEX ($/kW/year)",
    ),
    "vom_$/mwh_sent_out": dict(
        table="variable_opex_existing_committed_anticipated_additional_generators",
        # Keyed by "Power Station / Technology" (the cell can be either a
        # station name or a technology label).
        table_lookup="Power Station / Technology",
        table_value="Variable OPEX ($/MWh sent out)",
    ),
    "heat_rate": dict(
        table="heat_rates_existing_committed_anticipated_additional_generators",
        table_lookup="Power Station",
        table_value="Heat rate (GJ/MWh)",
        new_col_name="heat_rate_gj/mwh",
    ),
    "mlf": dict(
        # Single MLF table named (misleadingly)
        # `marginal_loss_factors_existing_generators` but carrying all ECAA
        # statuses plus batteries via a `Status` column.
        table="marginal_loss_factors_existing_generators",
        table_lookup="Power Station",
        table_value="MLF",
    ),
    "auxiliary_load_%": dict(
        table="auxiliary_load_existing_committed_anticipated_additional_generators",
        table_lookup="Power Station",
        table_value="Auxiliary load (% of generation)",
    ),
    # Outages live in `other_outages_existing_generators`, which schema
    # normalisation pivots to a single-year (2025-26) wide form.
    "partial_outage_derating_factor_%": dict(
        table="other_outages_existing_generators",
        table_lookup="Fuel type",
        table_value="Partial Outage Derating Factor (%)",
        generator_status="Existing",
    ),
    "mean_time_to_repair_full_outage": dict(
        table="other_outages_existing_generators",
        table_lookup="Fuel type",
        table_value="Full outage MTTR (hrs)",
        generator_status="Existing",
    ),
    "mean_time_to_repair_partial_outage": dict(
        table="other_outages_existing_generators",
        table_lookup="Fuel type",
        table_value="Partial outage MTTR (hrs)",
        generator_status="Existing",
    ),
}
""""
Existing, committed, anticipated and additional summary table columns mapped to
corresponding IASR tables and lookup information that can be used to retrieve values.

    `table`: IASR table name or a list of table names.
    `table_lookup`: Column in the table that acts as a key for merging into the summary
    `alternative_lookups`: A list of alternative key columns, e.g. "Project" as an
        alternative to  "Generator" in the additional projects table. If a lookup value
        is NA in the `table_lookup` column, it will be replaced by a lookup value from
        this list in the order specified.
    `table_value`: Column in the table that corresponds to the data to be merged in
    `alternative_values`: As for `alternative_lookups`, but for the data values in the
        table, e.g. "MLF - Generation" instead of "MLF" in the additional projects table
    `new_col_name`: The name that will be used to rename the column in the summary table
"""

_NEW_GENERATOR_STATIC_PROPERTY_TABLE_MAP = {
    "summer_peak_rating_%": dict(
        table="seasonal_ratings_new_entrants",
        table_lookup="Technology Type",
        table_value="Summer Peak (% of nameplate)",
    ),
    "summer_rating_mw": dict(
        table="seasonal_ratings_new_entrants",
        table_lookup="Technology Type",
        table_value="Summer Typical (% of nameplate)",
        new_col_name="summer_typical_rating_%",
    ),
    "winter_rating_mw": dict(
        table="seasonal_ratings_new_entrants",
        table_lookup="Technology Type",
        table_value="Winter (% of nameplate)",
        new_col_name="winter_rating_%",
    ),
    # "maximum_capacity_mw": dict(
    #     table="maximum_capacity_new_entrants",
    #     table_lookup="Generator type",
    #     table_value="Total plant size (MW)",
    # ),
    # "unit_capacity_mw": dict(
    #     table="maximum_capacity_new_entrants",
    #     table_lookup="Generator type",
    #     table_value="Unit size (MW)",
    # ),
    "maintenance_duration_%": dict(
        table="maintenance_new_entrants",
        table_lookup="Technology Type",
        table_value="Proportion of time out (%)",
    ),
    "fom_$/kw/annum": dict(
        table="fixed_opex_new_entrants",
        table_lookup="Generator",
        table_col_prefix="Fixed OPEX ($/kW sent out/year)",
    ),
    "vom_$/mwh_sent_out": dict(
        table="variable_opex_new_entrants",
        table_lookup="Generator",
        table_col_prefix="Variable OPEX ($/MWh sent out)",
    ),
    "heat_rate": dict(
        table="heat_rates_new_entrants",
        table_lookup="Technology",
        table_value="Heat rate (GJ/MWh)",
        new_col_name="heat_rate_gj/mwh",
    ),
    "mlf": dict(
        table="marginal_loss_factors_new_entrants",
        table_lookup="IASR ID",
        table_value="MLF",
    ),
    "auxiliary_load_%": dict(
        table="auxiliary_load_new_entrants",
        table_lookup="Generator",
        table_value="Auxiliary load (% of generation)",
    ),
    "partial_outage_derating_factor_%": dict(
        table="outages_new_entrants",
        table_lookup="Fuel type",
        table_value="Partial Outage Derating Factor (%)",
    ),
    "mean_time_to_repair_full_outage": dict(
        table="outages_new_entrants",
        table_lookup="Fuel type",
        table_value="Full outage MTTR (hrs)",
    ),
    "mean_time_to_repair_partial_outage": dict(
        table="outages_new_entrants",
        table_lookup="Fuel type",
        table_value="Partial outage MTTR (hrs)",
    ),
    "lifetime": dict(
        table="lead_time_and_project_life",
        table_lookup="Technology",
        table_value="Technical life (years)",
    ),
    "total_lead_time": dict(
        table="lead_time_and_project_life",
        table_lookup="Technology",
        table_value="Total lead time (years)",
    ),
}
"""
New entrant generators summary table columns mapped to corresponding IASR table and
lookup information that can be used to retrieve values.

    `table`: IASR table name or a list of table names.
    `table_lookup`: Column in the table that acts as a key for merging into the summary
    `alternative_lookups`: A list of alternative key columns, e.g. "Project" as an
        alternative to  "Generator" in the additional projects table. If a lookup value
        is NA in the `table_lookup` column, it will be replaced by a lookup value from
        this list in the order specified.
    `table_value`: Column in the table that corresponds to the data to be merged in
    `alternative_values`: As for `alternative_lookups`, but for the data values in the
        table
    `new_col_name`: The name that will be used to rename the column in the summary table
    `table_col_prefix`: The string that is present at the start of each column name
        in the table as a result of row merging in isp-workbook-parser, to be used
        for opex mapping to rename columns in the table.
"""

_ECAA_STORAGE_STATIC_PROPERTY_TABLE_MAP = {
    # Batteries share the consolidated generators table, so the storage code
    # reads the same source as the ECAA generator code, then filters by
    # technology_type containing "battery" downstream.
    "maximum_capacity_mw": dict(
        table="maximum_capacity_existing_committed_anticipated_additional_generators",
        table_lookup="Power Station",
        table_value="Installed capacity (MW)",
    ),
    "energy_capacity_mwh": dict(
        table="maximum_capacity_existing_committed_anticipated_additional_generators",
        table_lookup="Power Station",
        table_value="Storage Capacity (MWh)",
    ),
    "commissioning_date": dict(
        table="maximum_capacity_existing_committed_anticipated_additional_generators",
        table_lookup="Power Station",
        # Committed dates sit in `Commissioning date`, indicative ones in
        # `Indicative commissioning date` (see the ECAA generator map above).
        table_value="Commissioning date",
        alternative_values=["Indicative commissioning date"],
    ),
    "fom_$/kw/annum": dict(
        table="fixed_opex_existing_committed_anticipated_additional_generators",
        table_lookup="Power Station",
        table_value="Fixed OPEX ($/kW/year)",
    ),
    "round_trip_efficiency_%": dict(
        table="battery_properties",
        table_lookup="storage_name",
        table_value="Round trip efficiency_%",
    ),
    "charging_efficiency_%": dict(
        table="battery_properties",
        table_lookup="storage_name",
        table_value="Charge efficiency_%",
    ),
    "discharging_efficiency_%": dict(
        table="battery_properties",
        table_lookup="storage_name",
        table_value="Discharge efficiency_%",
    ),
}

_NEW_ENTRANT_STORAGE_STATIC_PROPERTY_TABLE_MAP = {
    "fom_$/kw/annum": dict(
        table="fixed_opex_new_entrants",
        table_lookup="Generator",
        table_col_prefix="Fixed OPEX ($/kW sent out/year)",
    ),
    "lifetime": dict(
        table="lead_time_and_project_life",
        table_lookup="Technology",
        table_value="Technical life (years)",
    ),
    "storage_duration_hours": dict(
        table="battery_properties",
        table_lookup="storage_name",
        table_value="Energy capacity_Hours",
    ),
    "round_trip_efficiency_%": dict(
        table="battery_properties",
        table_lookup="storage_name",
        table_value="Round trip efficiency_%",
    ),
    "charging_efficiency_%": dict(
        table="battery_properties",
        table_lookup="storage_name",
        table_value="Charge efficiency_%",
    ),
    "discharging_efficiency_%": dict(
        table="battery_properties",
        table_lookup="storage_name",
        table_value="Discharge efficiency_%",
    ),
}

"""
 _TEMPLATE_RENEWABLE_ENERGY_TARGET_MAP is a dictionary that maps template functions to
 lists of dictionaries containing the CSV file name, region_id and policy_id for each
 parsed table.
     `csv`: A single CSV file name (excluding file extension)
     `region_id`: region corresponding to that parsed table, to be inputted
         into templated table
     `policy_id`: policy corresponding to that parsed table, to be inputted
         into templated table links with the manually_extracted_table
         `policy_generator_types`
     `row_by_scenario` (optional): for a table with several target rows, text
         identifying the one row to keep in each IASR scenario
 """
_TEMPLATE_RENEWABLE_ENERGY_TARGET_MAP = {
    "template_renewable_share_targets": [
        {
            "csv": "vic_renewable_target",
            "region_id": "VIC",
            "policy_id": "vret",
        },
        {
            "csv": "sa_renewable_generation_target",
            "region_id": "SA",
            "policy_id": "sa_net_renewable",
        },
    ],
    "template_technology_capacity_targets": [
        {
            "csv": "nsw_roadmap_storage_power_capacity_trajectory",
            "region_id": "NSW",
            "policy_id": "nsw_eir_sto",
        },
        {
            "csv": "vic_storage_target",
            "region_id": "VIC",
            "policy_id": "vic_storage",
        },
        {
            "csv": "vic_offshore_wind_target",
            "region_id": "VIC",
            "policy_id": "vic_offshore_wind",
        },
    ],
    "template_renewable_generation_targets": [
        {
            "csv": "tas_renewable_target_trajectory",
            "region_id": "TAS",
            "policy_id": "tret",
        },
        # AEMO applies the legislated EIR row in Slower Growth and the IIO row in the
        # other scenarios. Either row sets the one NSW Roadmap generation constraint.
        {
            "csv": "nsw_roadmap_min_vre_generation_target",
            "region_id": "NSW",
            "policy_id": "nsw_iio_gen",
            "row_by_scenario": {
                "Slower Growth": "EIR",
                "Step Change": "IIO",
                "Accelerated Transition": "IIO",
            },
        },
    ],
}


# Subregion flow paths, from the IASR 2025-26 sub-region restructure: Victoria split into WNV (Western North Victoria),
# MEL (Melbourne) and SEV (South East Victoria), and NSA (Northern South Australia) added.
_SUBREGION_FLOW_PATHS = [
    "CQ-NQ",
    "CQ-GG",
    "SQ-CQ",
    "NNSW-SQ",
    "CNSW-NNSW",
    "CNSW-SNW",
    "SNSW-CNSW",
    "WNV-SNSW",
    "TAS-SEV",
    "WNV-SESA",
    "SESA-CSA",
    "CSA-NSA",
    "MEL-WNV",
    "SEV-MEL",
]

# ISP cost-scenario suffixes of the flow path and REZ augmentation cost tables.
_COST_SCENARIOS = ("slower_growth", "step_change", "accelerated_transition")

_FLOW_PATH_AGUMENTATION_TABLES = [
    "flow_path_augmentation_options_" + fp for fp in _SUBREGION_FLOW_PATHS
]

_REZ_CONNECTION_AGUMENTATION_TABLES = [
    "rez_augmentation_options_" + region for region in list(_NEM_REGION_IDS)
]

_FLOW_PATH_AUGMENTATION_COST_TABLES = {
    scenario: [
        f"flow_path_augmentation_costs_{scenario}_{fp}" for fp in _SUBREGION_FLOW_PATHS
    ]
    for scenario in _COST_SCENARIOS
}

_REZ_AUGMENTATION_COST_TABLES = {
    scenario: [
        f"rez_augmentation_costs_{scenario}_{region}"
        for region in list(_NEM_REGION_IDS)
    ]
    for scenario in _COST_SCENARIOS
}

_FLOW_PATH_AGUMENTATION_NAME_ADJUSTMENTS = {
    "Notional transfer level increase (MW) Note: Same increase applies to all transfer limit conditions (Peak demand, Summer typical and Winter reference)_Forward direction": "transfer_increase_forward_direction_MW",
    "Notional transfer level increase (MW) Note: Same increase applies to all transfer limit conditions (Peak demand, Summer typical and Winter reference)_Reverse direction": "transfer_increase_reverse_direction_MW",
}

_PREPATORY_ACTIVITIES_NAME_TO_OPTION_NAME = {
    "500kV QNI Connect (NSW works)": "NNSW–SQ Option 5",
    "500kV QNI Connect (QLD works)": "NNSW–SQ Option 5",
    "330kV QNI single circuit (NSW works)": "NNSW–SQ Option 1",
    "330kV QNI single circuit (QLD works)": "NNSW–SQ Option 1",
    "330kV QNI double circuit (NSW works)": "NNSW–SQ Option 2",
    "330kV QNI double circuit (QLD works)": "NNSW–SQ Option 2",
    "CQ-GG": "CQ-GG Option 1",
    "Sydney Southern Ring": "CNSW-SNW Option 2",
}

_REZ_PREPATORY_ACTIVITIES_NAME_TO_REZ_AND_OPTION_NAME = {
    "Darling Downs REZ Expansion(Stage 1)": ["SWQLD1", "Option 1"],
    "South East SA REZ": ["S1-TBMO", "Option 1"],
    "South West Victoria REZ Option 1": ["SWV1", "Option 1"],
    "South West Victoria REZ Option 1A": ["SWV1", "Option 1A"],
    "South West Victoria REZ Option 1B": ["SWV1", "Option 1B"],
    "South West Victoria REZ Option 1C": ["SWV1", "Option 1C"],
    "South West Victoria REZ Option 2A": ["SWV1", "Option 2A"],
    "South West Victoria REZ Option 2B": ["SWV1", "Option 2B"],
    "South West Victoria REZ Option 3A": ["SWV1", "Option 3A"],
    "South West Victoria REZ Option 3B": ["SWV1", "Option 3B"],
}

_PREPATORY_ACTIVITIES_OPTION_NAME_TO_FLOW_PATH = {
    "NNSW–SQ Option 5": "NNSW-SQ",
    "NNSW–SQ Option 1": "NNSW-SQ",
    "NNSW–SQ Option 2": "NNSW-SQ",
    "CNSW-SNW Option 2": "CNSW-SNW",
    "CQ-GG Option 1": "CQ-GG",
}

_ACTIONABLE_ISP_PROJECTS_NAME_TO_OPTION_NAME = {
    "Humelink": "SNSW-CNSW Option 1 (HumeLink)",
    "VNI West": "VIC-SNSW Option 1 - VNI West (Kerang)",
    "Project Marinus Stage 1": "TAS-VIC Option 1 (Project Marinus Stage 1)",
    "Project Marinus Stage 2": "TAS-VIC Option 2 (Project Marinus Stage 2)",
}

_ACTIONABLE_ISP_PROJECTS_OPTION_NAME_TO_FLOW_PATH = {
    "SNSW-CNSW Option 1 (HumeLink)": "SNSW-CNSW",
    "VIC-SNSW Option 1 - VNI West (Kerang)": "VIC-SNSW",
    "TAS-VIC Option 1 (Project Marinus Stage 1)": "TAS-VIC",
    "TAS-VIC Option 2 (Project Marinus Stage 2)": "TAS-VIC",
}

# Groups of augmentation options of one flow path or REZ of which at most one can be built
# (variants of one corridor or project), read from the option descriptions and prerequisites
# of the IASR 7.8 augmentation option tables. Stacked options keep the cheapest per MW.
_FLOW_PATH_ALTERNATIVE_OPTIONS = {
    "CNSW-SNW": [
        ["CNSW-SNW Option 6a", "CNSW-SNW Option 6b"],  # one Eraring-Bayswater line
        ["H-Newcastle", "H-Dapto"],  # one hydrogen port connection
        # Sydney Ring South; SNSW-CNSW Options 3 and 4 need "Option 3 or Option 4"
        ["CNSW-SNW Option 3 - Stage 1", "CNSW-SNW Option 4"],
    ],
    "CQ-GG": [["CQ-GG Option 1", "CQ-GG Option 2"]],  # Option 4 needs "1 or 2"
    "CSA-NSA": [  # one Bundey-Yunta-Narcoona line at 275, 330 or 500 kV
        ["CSA-NSA Option 1", "CSA-NSA Option 2", "CSA-NSA Option 3"]
        + ["CSA-NSA Option 4 Stage 1"]
    ],
    "MEL-WNV": [["MEL-WNV Option 1", "MEL-WNV Option 2"]],  # Option 3 needs "1 or 2"
    "NNSW-SQ": [  # one QNI-path line: 330 kV single or double circuit, or 500 kV
        ["NNSW-SQ Option 1", "NNSW-SQ Option 2", "NNSW-SQ Option 5"]
    ],
    "SESA-CSA": [  # one Bundey-Krongart line: 500 kV, 275 kV or HVDC
        ["SESA-CSA Option 2", "SESA-CSA Option 3", "SESA-CSA Option 4"]
    ],
    "SEV-MEL": [  # a Rowville or Cranbourne transformer, with or without series impedance
        ["SEV-MEL Option 1", "SEV-MEL Option 2", "SEV-MEL Option 3", "SEV-MEL Option 4"]
    ],
    "SNSW-CNSW": [
        ["SNSW-CNSW Option 3", "SNSW-CNSW Option 4"]
    ],  # double/single circuit
    "SQ-CQ": [["SQ-CQ Option 3", "SQ-CQ Option 5"]],  # REZ Q9 needs "Option 5 or 6"
    "TAS-SEV": [["TAS-SEV Option 2", "TAS-SEV Option 2A"]],  # Marinus Stage 2 or 2A
    "WNV-SESA": [  # one Krongart-Heywood line: 275 kV, 500 kV or HVDC
        ["WNV-SESA Option 1", "WNV-SESA Option 2", "WNV-SESA Option 3"]
    ],
}

_REZ_ALTERNATIVE_OPTIONS = {
    "MN1": [["Option 1", "Option 2", "Option 3", "Option 4"]],  # 1,200-1,300 MW designs
    "N13": [["Option 2", "Option 3"]],  # 2,400 MW after VNI West
    "SQ1": [["Option 1", "Option 2"]],  # 1,100 MW designs
    # South West Victoria routes; 1C and 5 extend 1A, 3C extends 3A to 3B's size
    "SWV1": [["Option 1A", "Option 2B", "Option 3A", "Option 3B", "Option 4"]],
    "T3": [["Option 1", "Option 1A"]],  # Option 2 needs "Option 1 or Option 1A"
}

# Transmission cost processing configurations
_FLOW_PATH_CONFIG = {
    "transmission_type": "flow_path",
    "in_coming_column_mappings": {
        "Flow path": "id",
        "Flow Path": "id",
        "Option Name": "option",
        "Option name": "option",
        "Option": "option",
        "Notional transfer level increase (MW) Note: Same increase applies to all transfer limit conditions (Peak demand, Summer typical and Winter reference)_Forward direction": "forward_capacity_increase",
        "Notional transfer level increase (MW) Note: Same increase applies to all transfer limit conditions (Peak demand, Summer typical and Winter reference)_Reverse direction": "reverse_capacity_increase",
        "Pre-requisite options": "prerequisites",
    },
    "out_going_column_mappings": {
        "id": "flow_path",
        "nominal_capacity_increase": "additional_network_capacity_mw",
    },
    "table_names": {
        "augmentation": _FLOW_PATH_AGUMENTATION_TABLES,
        "cost": _FLOW_PATH_AUGMENTATION_COST_TABLES,
    },
    "alternatives": _FLOW_PATH_ALTERNATIVE_OPTIONS,
    "mappings": {
        "prep_activities_name_to_option": _PREPATORY_ACTIVITIES_NAME_TO_OPTION_NAME,
        "option_to_id": _PREPATORY_ACTIVITIES_OPTION_NAME_TO_FLOW_PATH,
        "actionable_name_to_option": _ACTIONABLE_ISP_PROJECTS_NAME_TO_OPTION_NAME,
        "actionable_option_to_id": _ACTIONABLE_ISP_PROJECTS_OPTION_NAME_TO_FLOW_PATH,
    },
}

_REZ_CONFIG = {
    "transmission_type": "rez",
    "in_coming_column_mappings": {
        "REZ constraint ID": "id",
        "REZ / Constraint ID": "id",
        "REZ / constraint ID": "id",
        "Option": "option",
        "REZ": "rez",
        "REZ Name": "rez",
        "REZ name": "rez",
        "Additional network capacity (MW)": "nominal_capacity_increase",
        "Pre-requisite options": "prerequisites",
    },
    "out_going_column_mappings": {
        "id": "rez_constraint_id",
        "nominal_capacity_increase": "additional_network_capacity_mw",
    },
    "table_names": {
        "augmentation": _REZ_CONNECTION_AGUMENTATION_TABLES,
        "cost": _REZ_AUGMENTATION_COST_TABLES,
    },
    "alternatives": _REZ_ALTERNATIVE_OPTIONS,
    "prep_activities_mapping": _REZ_PREPATORY_ACTIVITIES_NAME_TO_REZ_AND_OPTION_NAME,
}


_VRE_RESOURCE_QUALITY_AND_TECH_CODES = {
    "Wind": ["WH", "WM"],
    "Wind - offshore (fixed)": "WFX",
    "Wind - offshore (floating)": "WFL",
    "Large scale Solar PV": "SAT",
    "Solar Thermal (15hrs storage)": "CST",
    "Solar Thermal (16hrs storage)": "CST",
}
