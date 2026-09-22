# Social licence premium -- source evidence

Verbatim evidence behind [`research.md`](research.md). Source ids match [`source_ledger.csv`](source_ledger.csv).

Sources S001 to S008 and S013 were read first-hand: the workbook and its cache from the share, and document text
extracted from the published PDFs and web pages named below. Sources S009 to S012 were located by web search and are
recorded with what the search established and nothing more; none of those four carries a quote, because none of those
documents was read directly.

## S001 -- AEMO 2024 ISP, Appendix 8, Social Licence

**Source:** <https://aemo.com.au/-/media/files/major-publications/isp/2024/appendices/a8-social-licence.pdf>, June 2024,
24 pages. Text extracted from the fetched PDF.

The only published AEMO figures that put a percentage on social licence for transmission and for REZ generation. Table 3
sets out the parameters; its transmission cost row reads, verbatim:

> "Project costs assumed to increase by approximately 15%. Reflects changes in work scope due to low social licence."

The detail column of that same row, verbatim:

> "Added a cost impost to transmission augmentations to reflect scope changes to routes and designs. The value of the
> cost increase was chosen by taking recent transmission project scope changes made by TNSPs in response to local
> stakeholder feedback, and then preparing a cost estimate change using AEMO's Transmission Cost Database to identify
> the project cost increase as a percentage. AEMO selected 15% as the increase as it was the approximate midpoint of the
> estimates prepared using recent major transmission project examples."

On what that 15% covers and what it is additional to, verbatim:

> "The scope changes were designed to capture small re-routings, re-design of towers, easement adjustments, and similar
> changes. The estimates also captured associated materials and labour, and were additional to existing cost estimates
> that already included scope changes and risks."

The delay row of the same table, verbatim:

> "Extending project lead times for all transmission augmentation options by two years."

The REZ generation cost row of the same table, verbatim:

> "REZ generation costs estimated to increase by approximately +5% to +60% based on private land parcel density, and
> applied to specific REZ generation costs by technology type (such as wind or solar)."

How that range is graduated, verbatim from footnote 2 on the same page:

> "For each REZ, the private land parcel density (parcels per square kilometre) was calculated, using state cadastral
> datasets. Less dense REZs (less than or equal to three parcels per square kilometre when compared to Central-West
> Orana REZ) had a minimum increase of 5% added to their generation costs. Only eight REZs were more dense than this
> threshold, and these REZs had proportional increases applied to their generation costs to reflect increased social
> licence costs. For example, Hunter-Central Coast REZ (N9) is 12 times more dense and a 60% uplift was applied."

On the result, verbatim:

> "The additional costs and delays to ODP projects associated with low social licence were found to result in an
> approximately $4 billion decrease in net market benefits."

On the extreme case, verbatim:

> "AEMO considers that increasing the Reduced Social Licence sensitivity parameters to the extent that no new renewable
> transmission or generation is developed would result in a scenario that resembles the 'counterfactual development
> path' outlined in Appendix 6. Cost Benefit Analysis. This effectively means that where coal generation is retired,
> substantial tranches of GPG, carbon-capture and storage, and batteries are installed instead. This would cost
> consumers an extra $18.5 billion relative to the ODP."

## S002 -- AEMO Draft 2026 ISP, Appendix A8, Social licence

**Source:** <https://www.aemo.com.au/-/media/files/major-publications/isp/draft-2026/a8-social-licence.pdf>, December
2025, 23 pages. Text extracted from the fetched PDF.

The successor appendix, which drops the priced sensitivity and folds social licence into the inputs instead. On that
change, verbatim:

> "In the 2024 ISP, AEMO included a social licence sensitivity analysis to model the potential impacts of low social
> licence on transmission project delays, transmission project costs, and REZ generation costs. There were some overlaps
> and similarities with the Constrained Delivery sensitivity which varied project lead times and the cost of generation
> and storage. Given that the Draft 2026 ISP now incorporates broader consideration of social licence factors and the
> Constrained Delivery sensitivity has been included for 2026, AEMO has not repeated the 'social licence' sensitivity
> analysis in the Draft 2026 ISP."

On social licence inside the transmission cost estimates, verbatim:

> "The Transmission Cost Database was updated this year to reflect cost increases due to supply chain pressures, market
> competition, project complexity, additional contracting costs, scope revision as more detailed assessments are
> completed, land price, and to factor in more time for community engagement and feedback."

On the route lengthening, verbatim:

> "Due to the need to avoid particularly complex areas, some early option transmission routes were lengthened by up to
> 20% from their straight-line estimate."

On social licence inside the lead times, verbatim:

> "AEMO also acknowledges the need for community engagement as part of any development, and a time allowance is included
> for this in the assumed 'lead time' for a transmission augmentation."

On what sets the REZ resource limits, verbatim:

> "REZ resource limits are set out in the ISP to estimate resources available for renewable energy developments. This
> availability is determined by existing land use (for example, agriculture) and environmental and cultural
> considerations (such as national parks), as well as the quality of wind or solar irradiance, and typical land use
> requirements for renewable energy generation."

On the land-use screen that produced the easement lengths, verbatim:

> "Scoring criteria were applied to land areas based on overall 'complexity' of use, resulting in more granular and
> detailed possible project routes and options. However, this was not a proxy for social licence or sentiment for
> localised projects."

That last sentence is the reason the premium proposed in `research.md` is not already inside the published costs: the
land-use screen shapes the route, but AEMO states it does not stand in for local social licence.

## S003 -- 2026 IASR workbook, Energy Policy Targets sheet

**Source:** `2026-isp-inputs-and-assumptions-workbook.xlsm`, sheet `Energy Policy Targets`, in the campaign input
directory's `iasr/2026 ISP Final/` folder on the share. Read with openpyxl in read-only mode; the sheet needs
`worksheet.reset_dimensions()` before iteration, or it truncates at row 327 and the landholder rows are missed entirely.

The three landholder payment schemes AEMO records, verbatim from rows 201, 207 and 264:

> "Under the Strategic Benefit Payments Scheme, private landowners hosting new high voltage transmission projects
> critical to the energy transformation and future of the electricity grid will be paid a set rate of $200,000 (in real
> 2022 dollars) per kilometre of transmission hosted, paid out in annual instalments over 20 years. AEMO will
> incorporate these payments as a category in the CBA."

> "Powerlink's SuperGrid Landholder Payment Framework offers payments to landowners that host new transmission
> infrastructure. To represent this framework, AEMO will apply a cost of $230,000 (in 2023 dollars) per km of new
> transmission, paid out in a lump sum -- noting that landholders can decide between a lump sum or annualised payments."

> "TasNetworks is establishing a Strategic Benefit Payments Scheme to compensate landholders impacted by major
> transmission developments for the North West Transmission Developments. These payments will be in addition to those
> afforded under the Land Acquisition Act 1993 (Tas). Once the specific details of the Strategic Benefit Payments Scheme
> are finalised, AEMO will include the costs in the ISP if appropriate."

No Victorian or South Australian landholder payment scheme appears anywhere in the workbook, and the Tasmanian row
carries no number, so of the four schemes only two enter AEMO's costs.

## S004 -- EnergyCo Strategic Benefit Payments Scheme

**Source:**
<https://www.energyco.nsw.gov.au/living-in-a-renewable-energy-zone/information-for-landholders/strategic-benefit-payment-scheme>.
Page fetched and read.

Confirms the workbook's rate from the administering agency, verbatim:

> "eligible landholders under the SBP Scheme will receive the equivalent of $200,000 in 2022 dollars, per kilometre"

> "Payments are made annually over a 20-year period"

> "adjusted annually for inflation using the Consumer Price Index"

The page lists the eligible projects as the Central-West Orana REZ Transmission Project, the Hunter Transmission
Project, the New England REZ network infrastructure project, Project EnergyConnect, HumeLink and VNI West. The A$200,000
per kilometre is a total paid in instalments, not an annual rate, which is what makes it comparable with the Queensland
lump sum and is how the derivation treats it.

## S005 -- Victorian landholder and neighbour payments

**Source:** announcements by the Victorian Government and reporting of them, located by web search:
<https://www.premier.vic.gov.au/landholder-payments-fairer-renewables-transition> and
<https://reneweconomy.com.au/victoria-sweetens-deal-on-transmission-build-out-with-promise-of-cash-for-landholders/>.

No quote: neither page was read directly, so the figures are recorded as what the search established rather than as
quoted text. The reported scheme pays transmission hosts A$200,000 per kilometre as A$8,000 per kilometre per year over
25 years, and pays significantly affected neighbours up to A$40,000 as a lump sum. The per-kilometre total matches the
NSW scheme, and the 25-year term rather than 20 is the only structural difference reported. Indexation was reported
inconsistently and is treated as unestablished. No Victorian REZ community benefit fund figure has been published.

## S006 -- 2026 IASR workbook, REZ resource limit violation penalty factor

**Source:** `2026-isp-inputs-and-assumptions-workbook.xlsm`, sheet `Build limits - REZs`, column header at row 6 and
values at rows 8 to 59. Read with openpyxl in read-only mode.

The column is headed, verbatim:

> "REZ resource limit violation penalty factor ($M/MW)"

Every REZ row carries 0.3. The two non-REZ rows, `V0` Non REZ Victoria and `N0` Non REZ NSW, carry 1.0. The workbook's
change log records how the non-REZ value arrived, verbatim:

> "Non-REZ Assumptions: Update to N0 and V0 land area. Inclusion of MW land use limits for wind and solar. Update of
> Resource Limit violation penalty factor to 1.0 $M/MW."

This is the closest published analogue to the campaign's question, because it is the price AEMO attaches to one megawatt
built past a REZ resource limit. It is a penalty chosen to make violation a last resort in the optimisation, not a
costed estimate, so `research.md` uses it to bound the proposed tranches rather than to set them.

## S007 -- 2026 IASR workbook, REZ land-use limits and the Accelerated Transition relaxation

**Source:** `2026-isp-inputs-and-assumptions-workbook.xlsm`, sheet `Build limits - REZs`, note 1 at row 61 and the
land-use limit columns at rows 8 to 59.

The note, verbatim:

> "A land use limit of 5% for onshore wind and 1% for solar is applied for all scenarios but Accelerated Transition
> scenario. The limit for the Accelerated Transition scenario is 25% and 5% for onshore wind and solar respectively.
> AEMO assumed an indicative land usage of 0.24 km2/MW for wind and 0.02km2/MW for solar."

The paired columns confirm the ratio arithmetically on every onshore REZ row: Q1 Far North Queensland carries 6,764 MW
of wind land-use limit against 33,821 MW in Accelerated Transition, and 16,234 MW of solar against 81,170 MW, both
exactly 5.0x. The two non-REZ rows are the exception, carrying the same limit in both columns.

AEMO therefore publishes a 5x land-use relaxation of its own, spanning the campaign's 1x-to-4x range, and attaches no
cost premium to it.

## S008 -- Tasmanian community engagement and benefit sharing guideline

**Source:** *Renewable Energy Development in Tasmania -- A Guideline for Community Engagement, Benefit Sharing and Local
Procurement*, Tasmanian Department of State Growth,
<https://www.recfit.tas.gov.au/__data/assets/pdf_file/0010/399205/Guideline_for_Community_Engagement,_Benefit_Sharing_and_Local_Procurement.pdf>.
Text extracted from the fetched PDF; the figures below are on page 15 of the guideline, page 18 of the file.

Verbatim:

> "To be consistent and to ensure there is a match between the scale of a project and the level of benefit, a benefit
> sharing budget is best calculated on a per MW basis, or as a percentage of project revenue. Current range of
> contributions from existing renewable energy projects are:
>
> - Wind Farms: $800-$1,800 per installed MW per year through to decommissioning;
> - Solar Farms: $150-$800 per installed MW per year through to decommissioning."

On what the budget excludes, verbatim from the same page:

> "The benefit sharing budget is directed at project neighbours and the impacted community, as well as the broader
> region where appropriate. However, does not include essential project requirements such as host landowner payments."

That exclusion is why these figures sit beside the per-kilometre schemes rather than overlapping them, and why they
price generation rather than transmission. The same guideline carries a Windlab case study; figures quoted from that
case study elsewhere could not be confirmed in the extracted text, so none is reproduced here.

## S009 -- Nexa Advisory, consumer cost of transmission delays

**Source:** *The Consumer Cost of Transmission Delays*, Nexa Advisory with Endgame Economics, July 2024,
<https://nexaadvisory.com.au/web/wp-content/uploads/2024/07/Nexa-Advisory-Consumer-Cost-of-Transmission-Delays-Report.pdf>.

No quote: the document was located by web search and not read directly. The figures the search established are a NSW
household bill increase of A$1,092 over 20 years for a three-year delay to transmission and A$3,984 for a seven-year
delay, with a NSW small business increase of A$7,716 and A$24,124 on the same two cases. These price the consequence of
delay for consumers, not a capital premium on capacity, so they enter the findings table as context and no conversion is
attempted.

## S010 -- AER and Deloitte social licence cost work

**Source:** AER, *Directions paper: Social licence for electricity transmission projects*, October 2023, and Deloitte,
*Assessment of Social Licence Costs for the Australian Energy Regulator*, March 2023, both at <https://www.aer.gov.au>.

No quote: both PDFs were located but their text could not be extracted. What the search established is that social
licence expenditure is recoverable within the regulatory investment test framework, and that the Deloitte work sets out
a framework for identifying which expenditure qualifies. No A$/km, A$/MW or percentage figure was found in either
document or in reporting of them. This is recorded as an absence rather than a number.

## S011 -- CSIRO GenCost

**Source:** *GenCost 2024-25 Final Report*, CSIRO, <https://www.csiro.au/en/research/technology-space/energy/GenCost>.

No quote: the PDF's text could not be extracted. No search result attributes any social licence, community benefit or
community-engagement cost allowance to GenCost, and its published scope is technology capital cost benchmarks for
levelised cost comparison. The absence of such an allowance is therefore recorded as probable and unconfirmed, not as
established.

## S012 -- Clean Energy Council, Renewable Resources Payment proposal

**Source:** Clean Energy Council,
<https://cleanenergycouncil.org.au/news-resources/clean-energy-council-calls-for-renewable-resources-payment-to-put-regional-communities-first>.

No quote: the page was located by web search and not read directly. The proposal is for a legislated fixed charge per
megawatt-hour of renewable electricity paid to host councils, modelled on mineral royalty schemes. No rate has been
published, so no figure enters the findings table.

## S013 -- Derived easement length and cost per megawatt

**Source:** `rez_augmentation_options_{NSW,QLD,SA,TAS,VIC}.csv` and `flow_path_augmentation_options_*.csv` in the
campaign input directory's `workbook_cache_final/` folder on the share.

No quote; these are data tables. Each REZ option row carries `Additional network capacity (MW)`, `Easement length (km)`
and `Expected cost ($2025 million)`; each flow-path option row carries the forward-direction notional transfer increase
in megawatts, `Easement length (km)` and `Indicative cost estimate ($2025, $ million)`. Restricting to rows with a
positive value in all three fields gives 65 REZ options and 33 flow-path options, from which the capacity-weighted
easement lengths of 0.1494 km/MW and 0.1121 km/MW and the capacity-weighted expansion costs of A$1,075,349/MW and
A$1,150,983/MW in `research.md` are computed as simple totals-over-totals.
