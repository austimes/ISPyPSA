# Carbon caps -- source evidence

Verbatim evidence behind [`research.md`](research.md). Source ids match [`source_ledger.csv`](source_ledger.csv).

## S001 -- The pressure ladder and the cap arithmetic

**Source:** [`analysis/hpc/manifest.py`](../../hpc/manifest.py).

On the ladder, verbatim:

> "The pressure ladder is fixed campaign data, declared at module level:
>
> * Every trajectory gets the uncapped A$0 chain (``c0``), the incumbent family.
> * Every trajectory gets the six cap schedules, named by their 2050 target intensity on the customer-delivered basis: 0.02 / 0.01 / 0.005 /
>   0.002 / 0.001 / 0.0005 t CO2e per MWh. Each schedule holds 2030 at 0.12 t/MWh, sets 2040 to the geometric mean of 0.12 and the target, and
>   holds 2060 at the target -- except the deepest schedule, whose 2060 rung tightens to 0.0001 t/MWh on the SOURCE basis.
> * Only ``iasr_central`` and ``iasr_stress`` get the price calibration chains ``c150``/``c300``/``c550``, which bracket the cap duals."

On the conversion to tonnes, verbatim:

> "Caps are always written into the solver as absolute annual tonnes: ``cap_t = delivery_fraction x intensity_delivered x Q_source_TWh x
> 1e6``, where ``Q_source`` is the trajectory's source NEM load for that year. A rung already quoted on the source basis skips the delivery
> factor. Every manifest row records its basis so no cap is ever quoted without one."

The ladder constant itself, verbatim:

> ```python
> CAP_ANCHOR_2030 = 0.12
>
> CAP_LADDER = (
>     CapSchedule("cap002", 0.02),
>     CapSchedule("cap001", 0.01),
>     CapSchedule("cap0005", 0.005),
>     CapSchedule("cap0002", 0.002),
>     CapSchedule("cap0001", 0.001),
>     CapSchedule("cap00005", 0.0005, rung_2060=Rung(0.0001, SOURCE_BASIS)),
> )
> ```

Nothing in this file or anywhere else in the fork records where 0.12 or the six targets come from.

## S002 -- The cap constraint

**Source:** [`analysis/hpc/instrumented_runner.py`](../../hpc/instrumented_runner.py), verbatim:

> "Absolute annual CO2e cap on generation combustion. Coefficients are the translator's isp_residual_co2_t_per_mwh (carrier total Scope-1
> CO2e factor x heat rate x (1 - capture_rate)), so CCS residual emissions at the configured capture rate are INSIDE the cap and captured CO2
> is not."

The coefficient it refers to, verbatim from [`src/ispypsa/translator/generators.py`](../../../src/ispypsa/translator/generators.py):

> ```python
> gross_t_per_mwh = heat_rate * carrier_factor_kg / 1000.0
> g["isp_residual_co2_t_per_mwh"] = gross_t_per_mwh * (1.0 - g["isp_capture_rate"])
> ```

## S003 -- The unserved-energy price and node limit

**Source:** [`analysis/hpc/solve.py`](../../hpc/solve.py), from the config template written for every period, verbatim:

> ```yaml
> unserved_energy:
>   cost: 10000.0
>   max_per_node: 100000.0
> ```

No basis for either value is recorded in this fork.

## S004 -- The acceptance rule

**Source:** [`analysis/sharp/deliverables.py`](../../sharp/deliverables.py).

On what the rule does, verbatim:

> "Load shedding. Deep caps can leave demand unserved at the A$10,000/MWh emergency price. A cell shedding more than `BOUNDARY_USE_PCT` of
> its demand is a BOUNDARY: it marks where the pressure setting stops being feasible on this fleet, so it is reported but never treated as a
> menu member, and it is dropped before the marginals are differenced. The unserved-energy generators carry no capital cost and are excluded
> from dispatch, marginal cost and capex everywhere in the post-processor, so the A$10,000/MWh penalty never enters a cost column."

On the threshold, verbatim:

> ```python
> # Above this share of demand left unserved, a cell is a boundary rather than a menu
> # member. A tenth of a percent is far above the rounding noise of a converged solve
> # and far below any shedding that would change the reported mix.
> BOUNDARY_USE_PCT = 0.1
> ```

On how a capped chain's price signal is recovered, verbatim:

> "Implied carbon price. A cap chain prices carbon at zero and exerts its pressure through the constraint, so its price signal is the cap's
> shadow price, read from the solve's constraint_duals.json and negated."

## S005 -- Load shedding in the deepest-cap run

**Source:** the limits inventory described in [`../rez_transmission_limits/source_data.md`](../rez_transmission_limits/source_data.md),
verbatim:

> "unserved_energy.cost | 10,000 A$/MWh | yes -- 157,934,633 MWh shed (26.83% of demand) | not part of the 2x-cap sensitivity; raising it does
> not relax a physical limit"

That shed energy divided by 26.83% gives about 589 TWh, which matches the `iasr_stress` 2060 source load of 586 TWh to within half a per
cent, so the figure is on the same demand basis as the plan.
