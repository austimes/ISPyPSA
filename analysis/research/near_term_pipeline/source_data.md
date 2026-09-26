# Near-term pipeline -- source evidence

Verbatim evidence behind [`research.md`](research.md). Source ids match [`source_ledger.csv`](source_ledger.csv).

Every source except S004, S006 and S007 was read first-hand: two data files in this repository, two cache tables and
four templated input files from the share. S004 carries a quote from a fetched web page but not from the underlying
AEMO document, which was not read for this topic. S006 and S007 restate figures already read and reported by
[`../aemo_scenario_cost/`](../aemo_scenario_cost/) rather than being read again here.

## S001 -- AEMO draft 2026 ISP, Step Change CDP4 capacity series

**Source:** [`../../../iasr outputs/NEM-aemo2026draft-step_change-CDP4 (ODP)-capacity.csv`](../../../iasr%20outputs/)
in this repository.

No quote; a data table of annual installed capacity in whole gigawatts by fuel. The 2030 column, which is the yardstick
the allowance is measured against:

| Fuel | 2030 capacity (GW) |
| ---- | -----------------: |
| Wind | 26 |
| Solar (Utility) | 32 |
| Solar (Rooftop) | 36 |
| Coal | 13 |
| Gas | 12 |
| Hydro | 7 |
| Demand Response | 1 |
| Bioenergy | 0 |
| Distillate | 0 |

Rooftop solar sits on the demand side of the campaign model and is not part of any allowance. There is no storage column
in the file, which is why the storage allowance rests on S004 instead.

## S002 -- IASR workbook cache, maximum capacity of existing, committed, anticipated and additional generators

**Source:** `maximum_capacity_existing_committed_anticipated_additional_generators.csv` and
`existing_committed_anticipated_additional_generator_summary.csv` in the campaign input directory's
`workbook_cache_final/` folder on the share.

No quote; data tables. The maximum-capacity table has 519 rows with columns `IASR ID`, `Power Station`, `Status`,
`Technology`, `Region`, `Installed capacity (MW)`, `Storage Capacity (MWh)`, `Commissioning date`, `Policy` and
`Indicative commissioning date`. Its `Status` values are `Existing`, `Committed`, `Anticipated` and
`Additional policy-supported project`, plus one placeholder row.

What matters for `research.md` is the commissioning date coverage of the battery rows:

| Status | Battery rows | Capacity (GW) | Rows with an empty `Commissioning date` | Rows with neither date |
| ------ | -----------: | ------------: | --------------------------------------: | ---------------------: |
| Committed | 39 | 8.81 | 0 | 0 |
| Anticipated | 48 | 11.48 | 48 | 0 |
| Additional policy-supported project | 29 | 8.05 | 0 | 0 |

Every committed battery in the workbook carries a firm commissioning date, and every anticipated battery carries an
indicative one instead. The workbook is not missing any date, which is what establishes that the 29 undated rows in the
templated file are a templating loss rather than an input gap.

## S003 -- Templated inputs of the reference run's 2030 solve

**Source:** `ispypsa_inputs/ecaa_generators.csv`, `ispypsa_inputs/ecaa_batteries.csv`, `pypsa_friendly/generators.csv`
and `pypsa_friendly/batteries.csv` under
`outputs/2026-09-21T16.08_ext41_rezx4_corrx4/runs/ext_central_c0_2030__cost_optimal/` in the campaign output directory on
the share.

No quote; data tables written by the fork's own model builder, so they are the roster a campaign run actually holds
rather than a reconstruction of it. The generator roster is the 329 rows of `pypsa_friendly/generators.csv` whose name
appears in `ecaa_generators.csv`, and the storage roster is the 88 rows of `ecaa_batteries.csv`. Both are already
date-filtered to 2030, which is why the roster totals of 20.107 GW of wind and 19.600 GW of solar fall short of the
21.7 GW and 24.2 GW the workbook lists in total: the remainder commissions after 2030.

`ecaa_batteries.csv` carries `storage_name`, `isp_resource_type`, `technology_type`, `status`, `region_id`,
`sub_region_id`, `rez_id`, `fuel_type`, `fom_$/kw/annum`, `maximum_capacity_mw`, `storage_duration_hours`,
`commissioning_date`, `closure_year`, `lifetime` and the three efficiency columns. Its `commissioning_date` column is
empty on 63 of its 88 rows, of which 29 are `Committed`:

| Status | Rows | Capacity (GW) | Rows with an empty `commissioning_date` | Capacity of those rows (GW) |
| ------ | ---: | ------------: | --------------------------------------: | --------------------------: |
| Existing | 36 | 4.840 | 34 | 4.023 |
| Committed | 31 | 9.189 | 29 | 6.739 |
| Anticipated | 20 | 5.860 | 0 | - |
| Additional policy-supported project | 1 | 0.810 | 0 | - |

The 29 committed rows and their workbook commissioning dates, which S002 shows are present in the input and dropped in
templating:

| Battery | MW | Workbook commissioning date |
| ------- | -: | --------------------------- |
| Waratah Super Battery | 843.8 | 2025-01-01 |
| Western Downs Battery | 509.6 | 2025-12-01 |
| Liddell BESS | 500.0 | 2026-02-01 |
| Gnarwarre BESS | 470.4 | 2027-11-01 |
| Orana BESS | 416.6 | 2026-06-01 |
| Wooreen Energy Storage System | 350.6 | 2027-12-01 |
| Mortlake Battery | 300.0 | 2026-07-01 |
| Tarong BESS | 300.0 | 2026-01-01 |
| Woolooga BESS | 281.0 | 2026-09-01 |
| Supernode BESS 2 | 259.9 | 2026-06-01 |
| Supernode BESS 1 | 259.9 | 2026-01-01 |
| Pine Lodge BESS | 250.0 | 2026-10-01 |
| Eraring Big Battery 2 | 240.0 | 2027-03-01 |
| Mornington BESS | 240.0 | 2026-02-01 |
| Brendale BESS | 205.0 | 2026-06-01 |
| New England Solar Farm BESS | 200.0 | 2026-06-01 |
| Bennetts Creek BESS | 176.4 | 2028-03-01 |
| Calala BESS 2 | 158.3 | 2026-12-01 |
| Bungama Solar BESS | 150.0 | 2026-05-01 |
| Terang BESS | 144.4 | 2026-06-01 |
| Templers BESS | 111.0 | 2025-08-01 |
| Calala BESS 1 | 108.1 | 2026-12-01 |
| Fulham Solar Farm BESS | 64.1 | 2027-09-01 |
| Clements Gap BESS | 60.0 | 2026-01-01 |
| Limondale BESS | 50.0 | 2026-03-01 |
| Tailem Bend Battery Project | 41.5 | 2024-01-01 |
| Quorn Park BESS | 27.6 | 2026-12-01 |
| Lincoln Gap Wind Farm BESS | 10.8 | 2026-03-01 |
| Lockhart Hybrid Facility - Battery | 10.0 | 2026-06-01 |

Every date is 2028 or earlier, so on a chain whose first milestone is 2030 all 29 would be in service anyway and the
practical consequence for this campaign is nil. The loss is total rather than partial: no committed battery in the
templated file keeps its date, and the only two dated committed rows are the pumped hydro units the fork's own PHES patch
adds, Snowy 2.0 and Kidston.

A second and separate loss sits alongside it. Ten committed batteries totalling 2,070.5 MW appear in the workbook's
maximum-capacity sheet and nowhere in its summary sheet, which is the roster the templater reads, so they never enter the
model at all: Elaine BESS (309.6 MW), Bulabul BESS 1 (300.0), Williamsdale BESS (250.0), Blind Creek Solar Farm BESS
(245.7), Bellambi Heights BESS (204.0), Tailem Bend BESS Stage 3 (204.0), Pelican Point BESS (200.0), Summerfield BESS 1
and 2 (153.7 each) and Goulburn River Solar Farm BESS (49.8). The workbook itself is consistent: ISPyPSA's parser
configuration (`src/ispypsa/iasr_table_caching/parser_configs/7.8/summary_mapping.yaml`) read the summary sheet only to
row 648 while its data runs to row 732, which also dropped 29 anticipated batteries and 25 wind and solar generators.

## S004 -- AEMO draft 2026 ISP grid-scale storage milestone as reported

**Source:** *Renewables on rise as AEMO lays out roadmap for energy transition*, pv magazine Australia, 10 December 2025,
<https://www.pv-magazine-australia.com/2025/12/10/renewables-on-rise-as-aemo-lays-out-roadmap-for-energy-transition/>.
Page fetched and read; the draft ISP itself was not read for this topic.

Verbatim from the article, reporting AEMO's draft optimal development path:

> "33 GW of dispatchable, grid-scale battery and pumped-hydro energy storage would be needed by 2050, with 27 GW by
> 2030."

The article's wind and solar sentences, quoted in full under S009 of
[`../build_rate_premium/source_data.md`](../build_rate_premium/source_data.md), match the CDP4 capacity file exactly at
all six milestones, which is what gives this storage sentence its credibility. It remains secondary reporting of a
combined battery and pumped hydro figure, so the storage allowance derived from it is low confidence.

## S005 -- AEMO scenario emissions intensity series

**Source:** [`../aemo_scenario_intensity/aemo_scenario_intensity.csv`](../aemo_scenario_intensity/aemo_scenario_intensity.csv)
in this repository.

No quote; a data table with columns `year`, `scenario`, `generation_twh`, `emissions_mt` and `t_co2e_per_mwh`, covering
2010 to 2050 for the three draft 2026 ISP scenarios. The Step Change rows at the campaign's five milestones are
reproduced in `research.md`. The derivation of the series, and its own confidence, are in
[`../aemo_scenario_intensity/research.md`](../aemo_scenario_intensity/research.md); this topic only records that the base
chain's cap schedule now reads from it.

## S006 -- AEMO final 2026 ISP chart data, Step Change capacity at 2029-30

**Source:** [`../aemo_scenario_cost/source_data.md`](../aemo_scenario_cost/source_data.md), S006 there: AEMO 2026 ISP
chart data workbook, `2026-isp-chart-data.xlsx`, sheet "Figure 1" (titled "NEM capacity (GW, 2010 to 2050, Step Change,
financial year ending)", values in MW) and sheet "Figure 20". The 2029-30 column, verbatim from that topic: "Onshore
wind" 29818.2, "Utility solar" 31188.8, "Utility storage" 35779.8; Figure 20 splits utility storage into Snowy 2.0
(2.202 GW), deep, medium and shallow storage, of which medium and shallow storage (batteries) together are 33.3 GW in
2029-30. This is the final 2026 ISP, superseding the draft-ISP CDP4 series (S001) as the yardstick for the new-entrant
allowance.

## S007 -- IASR roster commissioned by 1 July 2029

**Source:** [`../aemo_scenario_cost/research.md`](../aemo_scenario_cost/research.md#capital-scope), table under "Capital
scope": "IASR roster by 1 July 2029 (GW)" column, wind 17.6, utility solar 22.9, batteries 28.2. That topic sums the
same maximum-capacity roster as S002 here, filtered to a commissioning date on or before 1 July 2029, for its own
cost-gap decomposition; this topic reuses the same totals as the roster already in the model when the final-ISP
allowance is measured.
