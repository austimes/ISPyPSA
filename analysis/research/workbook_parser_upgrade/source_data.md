# Workbook parser configuration -- source evidence

Verbatim evidence behind [`research.md`](research.md). Source ids match [`source_ledger.csv`](source_ledger.csv); authored assumption ids
match [`assumptions_ledger.csv`](assumptions_ledger.csv).

## S001 -- isp-workbook-parser 2.9.0 changelog

**Source:** `CHANGELOG.md` of the `isp-workbook-parser` 2.9.0 release, <https://github.com/Open-ISP/isp-workbook-parser>.

On the new workbook version, verbatim:

> Support for IASR workbook version 7.8 (final 2026 ISP workbook).

On the sanitiser, verbatim:

> Fixed sanitiser handling of `[footnote]`-style markers and notes containing `$` amounts

The same release renames `flow_path_augmentation_cost_slower_growth_CNSW-NNSW` to
`flow_path_augmentation_costs_slower_growth_CNSW-NNSW` for workbook versions 7.3, 7.5 and 7.8.

## S002 -- AEMO 2026 ISP final inputs and assumptions workbook

**Source:** `iasr/2026 ISP Final/2026-isp-inputs-and-assumptions-workbook.xlsm` in both input packages under `$IO_DIR/inputs`; its Change
Log sheet reports version 7.8. The v4 package's copy is byte-identical to v3's, so every cache difference comes from the parser and its
configuration, not from the workbook.

## S003 -- The two parsed caches

**Source:** `$IO_DIR/inputs/2026-09-23T19.42_isp2026_final_v3/workbook_cache_final/` and
`$IO_DIR/inputs/2026-09-25T14.13_isp2026_final_v4/workbook_cache_final/`, both holding the same 153 CSV files. The v4 cache was built by
`build_local_cache(<v4>/workbook_cache_final, <workbook>, "7.8", trace_directory=<v4>/traces)` with `isp-workbook-parser` 2.9.0 and
parser validation checks on. The per-table comparison is [`table_diff.csv`](table_diff.csv), written by
[`plot_cache_diff.py`](plot_cache_diff.py).

Example cell, `flow_path_augmentation_options_CSA-NSA`, column `Indicative cost estimate ($2025, $ million)`, v3 then v4, verbatim:

> ```text
> 1749.5$23 million of this amount relates to approved early works costs and other incurred costs. [...]
> 1749.5
> ```

Example row, `variable_opex_new_entrants`, removed in v4, verbatim from v3:

> ```text
> 1. Sourced from Aurecon 2024 Energy Technology Cost and Technical Parameter Review, cost adjusted.
> ```

## S004 -- The two table configurations

**Source:** the 2.9.0 configurations installed at `.venv/Lib/site-packages/isp_table_configs/7.8/`, and the draft-derived configuration
at `src/ispypsa/iasr_table_caching/parser_configs/7.8/` in this repository's history before its removal (for example commit `53fba3b`).
The auxiliary-load entry, draft-derived then 2.9.0, verbatim:

> ```text
> end_row: 648
> end_row: 732
> ```
