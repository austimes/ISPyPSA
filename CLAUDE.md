# Claude Coding Preferences for ISPyPSA

## Code Style

### Guiding principle

**Readability first.** Favour clarity over DRY or efficiency. A little repetition is fine if it
makes the code easier to follow. Optimise for a reader who hasn't seen the codebase before.

### Orchestrator + helper pattern

High-level functions should read like a narrative — a sequence of descriptive verb-phrase calls
that tell the story of what the function does. Push all data manipulation into private (`_`)
helper functions.

```python
def template_network_transmission_paths(iasr_tables, scenario):
    paths = _extract_flow_paths(iasr_tables["flow_path_transfer_capability"])
    paths = _add_transfer_limits(paths, iasr_tables["interconnector_transfer_capability"])
    paths = _filter_to_scenario(paths, scenario)
    return paths
```

### Helper function guidelines

- **≤ 10 lines** of actual logic (excluding docstrings/blank lines) for any function that
  touches or transforms data.
- **Private by default** — prefix with `_` unless the function is part of the public API.
- **Descriptive names** — the name should make the orchestrator readable without needing to
  look at the helper's body. Prefer verb phrases: `_extract_*`, `_add_*`, `_filter_*`,
  `_map_*`, `_merge_*`.
- **Single responsibility** — each helper does one thing. If a helper needs an internal
  comment explaining a second step, it should probably be two helpers.

### Clarity over cleverness

- **Avoid positional access** like `iloc[:, 0]` — use named column access (e.g.
  `df["Flow Paths"]`) so the code states what it means.
- **Comment non-obvious regex** — add a concrete example of the input being matched and
  annotate each capture group.
- **Prefer explicit data over clever detection.** If the set of special cases is small and
  stable, declare them as data rather than building logic to infer them from surrounding
  context.

### Control flow

- **Keep it flat.** Prefer simple, linear control flow even if it means some repetition.
- **One level of nesting max** for `if` and `for` statements. If you find yourself writing
  nested loops or nested conditionals, extract the inner block into a helper function.
  The exception is when nesting genuinely is the simplest way to express the logic — but
  that should be rare.

### Non-defensive code

Write non-defensive code by default. Trust design decisions and caller contracts. Don't add
`None` checks, fallback logic, or `try/except` blocks unless explicitly needed or revealed
through testing. Let the code fail clearly when preconditions aren't met.

No backwards compatibility unless explicitly requested — update all call sites directly.

## Logging

Logging surfaces things a user or operator wants to know during a template/translation
run that aren't visible from the returned DataFrames. Errors that should halt the run
are `raise`d, not logged.

### Levels

- **INFO** — used for:
  - The top of a public template/translator orchestrator
    (`logging.info("Creating a template for X")`). Gives a progress trace for long runs.
  - Start and completion of long-running CLI operations (downloads, deletions, file
    generation).
  - Silently dropped or filtered data — rows that appear in the input but not in the
    output (e.g. unmatched options dropped by an inner merge).

- **WARNING** — for data integrity issues the run will tolerate but the caller might
  want to act on:
  - Per-row computations that fail and produce NaN in the output, including paths/REZs
    that were missing from the IASR tables and will receive a default downstream.
  - Empty templated tables that mean a class of components won't appear in the model.
  - User-supplied filter inputs that match nothing in the data.
  - Missing entire input IASR tables.
    *(Note: this category will be deprecated once table-schema-based validation lands —
    that layer should surface missing tables instead.)*

- **DEBUG and ERROR are not used.** Errors are raised as exceptions.

### What not to log

- The successful happy path inside a helper.
- Individual row contents — aggregate into a `sorted(...)` list and log once. The
  fuzzy-match log in `helpers.py` is an exception: it logs each non-exact match
  individually so the user can audit name-matching decisions one by one.
- Anything readily inspected from the returned DataFrame.
- The same condition at multiple call sites — log once at the source where the cause
  is visible.

### Style

- Use f-strings. Wrap collections with `sorted(...)` so messages are stable across runs
  and tests can rely on them.
- Name the specific input/table/region:
  `f"Missing augmentation tables: {missing}"` beats `"some tables are missing"`.
- One summary line over many per-row lines (except the fuzzy-match exception above).

### Tests

Log lines that surface non-obvious data behaviour should be covered with `caplog`. Assert the
**full emitted log message** in one substring check, not a marker plus per-name positive/negative
checks. Because logging style wraps collections in `sorted(...)`, the message is deterministic, so
asserting it whole pins the marker, the listed names, and the absence of any others all at once —
and it doesn't break when an unrelated log line later mentions one of the names you were
negatively checking for.

```python
def test_logs_paths_with_no_capacity(caplog):
    with caplog.at_level("WARNING"):
        my_function(inputs_with_missing_data)
    assert (
        "Flow paths with no capacity data in IASR table "
        "(default will be applied downstream): ['MN-SA']"
    ) in caplog.text
```

Cover both the firing case and a negative case (no log when data is complete).

## Testing

### Test structure

Tests follow a strict ordering: **inputs → function call → expected → assertion.**

Use the `csv_str_to_df` fixture to create readable DataFrame inputs and expected outputs. Place
each `assert_frame_equal` immediately after its expected DataFrame definition. Only include
columns in test inputs that the code actually accesses.

**Always assert with `pd.testing.assert_frame_equal` against a full expected DataFrame.** Don't
substitute row-count checks, set membership on a column, per-cell `iloc[...]` lookups, or
`pd.isna(...)` probes — they hide off-by-one, ordering, and stray-column bugs and read worse than
a single side-by-side comparison. The same applies to empty results: build an empty expected
DataFrame with a header-only `csv_str_to_df("path_id,  geo_from, ...")` call and compare, rather
than asserting `result.empty` plus `list(result.columns) == [...]` separately.

```python
def test_my_function(csv_str_to_df):
    input_data = csv_str_to_df("""
        name,   value
        item1,  100
        item2,  200
    """)

    result = my_function(input_data)

    expected = csv_str_to_df("""
        name,   processed_value
        item1,  150
        item2,  250
    """)
    pd.testing.assert_frame_equal(
        result.sort_values("name").reset_index(drop=True),
        expected.sort_values("name").reset_index(drop=True),
    )
```

### Empty DataFrame handling

Missing data is represented as a DataFrame with all expected columns but no rows ("all columns,
no rows"). This is enforced by schema validation at module boundaries, so internal functions can
rely on receiving complete DataFrames and never need to check for `None` or missing tables.

Functions must handle empty DataFrames gracefully — pandas operations like filtering, groupby,
and concat naturally handle this without special-case code.

### Combinatorial edge cases

Functions with multiple input DataFrames must be tested with:

- Table A empty, Table B populated
- Table A populated, Table B empty
- Both tables empty

```python
def test_both_empty(csv_str_to_df):
    table_a = pd.DataFrame(columns=["id", "value"])
    table_b = pd.DataFrame(columns=["id", "name"])

    result = my_function(table_a, table_b)

    expected = csv_str_to_df("""
        id,  value,  name
    """)
    pd.testing.assert_frame_equal(result, expected, check_dtype=False)
```

Use `pd.DataFrame(columns=[...])` for empty *inputs* (where shared module-level column
constants like `_FLOW_PATH_COLUMNS` make the construction tighter), and header-only
`csv_str_to_df` for empty *expected outputs* (so the assertion's expected shape lives in the
same readable form as every other expected DataFrame in the test).

### Comparing DataFrames

- Sort both sides before comparison when row order doesn't matter
- Use `check_exact=False` or `rtol=1e-5` for floating point comparisons
- Represent NaN cells in `csv_str_to_df` as a blank field after the comma — e.g.
  `A-B,    ,   ,` produces a row with `path_id="A-B"` and NaN for the remaining columns.
  Use this for collapsed/missing-data rows instead of `iloc` + `pd.isna` probes.
- Use `check_dtype=False` when type precision isn't critical (e.g. NaN columns)

## Development Environment

Use `uv` for package management. Key commands:

```bash
uv sync                  # Install dependencies from lock file
uv run pytest tests/     # Run tests
uv run pytest tests/test_foo.py::test_bar -v  # Run a specific test
uv run pre-commit run --all-files             # Run linters
```

## Version Control

- Only commit when explicitly requested
- Commit messages should focus on the "why" rather than the "what"

---

# Project context: ShARP electricity supply campaign

The sections above are upstream ISPyPSA coding style preferences. This section is project-specific context for the
**ShARP electricity supply campaign** in this fork. Read both before doing any new work.

## The fork's purpose

This fork runs a National Electricity Market (NEM) capacity-expansion campaign - a grid of chained yearly solves across
demand trajectories and carbon-pressure settings - and turns the results into CSV deliverables for ShARP, the
whole-of-economy optimisation model those results feed. It wraps `src/ispypsa/`, the Australian Energy Market
Operator's (AEMO) capacity-expansion model for its Integrated System Plan (ISP), with campaign-specific model patches, a
Slurm cluster workflow, the ShARP emitters, and a plotly dashboard.

## What's in this fork

Everything fork-specific lives under `analysis/`, in four sub-packages, and the whole campaign runs as five `msm`
commands; [`analysis/README.md`](analysis/README.md) holds the sub-package map, the `IO_DIR` input and output layout and
the command-by-command workflow. Read it first, then
[`analysis/MODELLING_ASSUMPTIONS.md`](analysis/MODELLING_ASSUMPTIONS.md) for every way this fork's model differs from
upstream ISPyPSA and from AEMO's published inputs, and [`analysis/REPRODUCING.md`](analysis/REPRODUCING.md) for how to
reproduce an electricity investment history end to end.

## Rules for work in this fork

- **Nothing fork-specific goes under `src/` or `docs/`**: every campaign addition, code and documentation alike, stays
  inside `analysis/`. Corrections to the model itself belong in `src/ispypsa/`, in that package's own style, and must
  make sense to any ISPyPSA user.
- Every model difference from upstream ISPyPSA or from AEMO's published inputs is recorded in
  [`analysis/MODELLING_ASSUMPTIONS.md`](analysis/MODELLING_ASSUMPTIONS.md), under one of its four headings: upstream
  fixes, fork input patches, authored assumptions with no AEMO source, and campaign method.
- Every input and run product lives under one directory, `$IO_DIR`, set in `.env` (copy `.example.env`) and mounted at
  the same path on the workstation and on the cluster. Inputs and launches are both timestamp-versioned directories,
  `<YYYY-MM-DDTHH.MM>_<name>`, flat under `$IO_DIR/inputs/` and `$IO_DIR/outputs/`. Never write a run product anywhere
  else, and never hard-code a path that `analysis.env` can resolve.
- Run every step through the `msm` command line (`uv run msm --help`), never by calling a script path or ISPyPSA's own
  package builder: `msm` is the only path that applies the fork's model patches.
- Write the laziest code that works - shortest diff, standard library and existing helpers before anything new - and
  leave no commentary in the code about the change itself.
- Every numeric assumption the campaign relies on is researched under `analysis/research/<topic>/`, one folder per
  assumption area, following the ShARP `research-role` conventions: `research.md` (what the model does, the derivation,
  a table of the numbers, and a `confidence: high|medium|low` line with a one-line rationale per derivation),
  `source_data.md` (numbered sources with a link or file path and a verbatim quote where the document is available;
  never invent a quote or page number, say so when none exists), `source_ledger.csv` and `assumptions_ledger.csv` with
  the fixed column sets, and a `plot_*.py` that writes html and png with plotly wherever a plot earns its place. Tables
  over prose; cite files by path; keep every research doc stateless. Update the topic folder in the same change as the
  code or data it describes, and add new topics to `analysis/research/README.md`.
