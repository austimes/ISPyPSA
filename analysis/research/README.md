# Campaign model research

Evidence pack for the assumptions built into this fork's extension campaign. One folder per assumption area. Each folder holds
`research.md` (what the model does, how each number was derived, a confidence tag per derivation), `source_data.md` (numbered sources with a
verbatim quote wherever the document is readable from this repo), `source_ledger.csv`, `assumptions_ledger.csv`, and a `plot_*.py` script with
its HTML and PNG output where a picture earns its place.

| Topic | What it bounds | Plot |
|---|---|---|
| [`demand_plan/`](demand_plan/) | The five demand trajectories the campaign grid is built over | [`demand_trajectories.png`](demand_plan/demand_trajectories.png) |
| [`rez_transmission_limits/`](rez_transmission_limits/) | Renewable energy zone (REZ) transmission, resource and land-use ceilings | [`binding_limits.png`](rez_transmission_limits/binding_limits.png) |
| [`hydro_energy_budget/`](hydro_energy_budget/) | Annual water available to conventional hydro | [`hydro_budget.png`](hydro_energy_budget/hydro_budget.png) |
| [`biomass/`](biomass/) | Biomass fuel tranches, the capacity cap, and biomass emissions under a carbon cap | [`biomass_limits.png`](biomass/biomass_limits.png) |
| [`pumped_hydro_menu/`](pumped_hydro_menu/) | The pumped hydro energy storage (PHES) candidate menu and its site ceilings | [`phes_menu.png`](pumped_hydro_menu/phes_menu.png) |
| [`carbon_caps/`](carbon_caps/) | The carbon pressure ladder, the cap tonnage arithmetic and the load-shedding rule | [`carbon_caps.png`](carbon_caps/carbon_caps.png) |
| [`campaign_method/`](campaign_method/) | Chain structure, time sampling, solver settings and the 2060 hold | [`campaign_sampling.png`](campaign_method/campaign_sampling.png) |
| [`aemo_scenario_intensity/`](aemo_scenario_intensity/) | Per-year AEMO scenario emissions intensity the dashboard draws as a sanity reference | [`aemo_scenario_intensity.png`](aemo_scenario_intensity/aemo_scenario_intensity.png) |

Conventions used throughout:

- Sources carry role-local ids `SNNN`, authored assumptions carry `ANNN`; a number in a table cites one or the other, never both, and a number
  whose origin could not be established is labelled unknown rather than attributed.
- Every quoted figure is either read from a file in this repository (cited by path) or quoted verbatim from a document readable from this
  repository; where no local copy exists, `source_data.md` says so instead of carrying an invented quote or page number.
- Plots are built with plotly and saved as both HTML and PNG beside their script; run them with `uv run --with kaleido python <script>`.
