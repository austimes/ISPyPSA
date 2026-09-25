"""One command line for the campaign: ``uv run msm <command> [args]``.

Every command keeps its own logic and its own ``main``; this module only binds each
``main`` to a command name, so the team has one entry point instead of a set of script
paths. Commands are registered by import path, so a module and its heavy dependencies load
only when its command runs; cyclopts derives each command's options from its ``main``
signature, which is why no argument parsing lives here.

On the cluster's compute nodes, which have no internet, run it as
``uv run --no-sync msm <command>``.
"""

from cyclopts import App

app = App(name="msm", help="ShARP electricity campaign command line.")

app.command(
    "analysis.hpc.launch:main",
    name="launch",
    help="Prepare a campaign launch and submit its chains to Slurm.",
)
app.command(
    "analysis.hpc.solve:main",
    name="solve",
    help="Solve one chain of single-period ISPyPSA runs, one per milestone year.",
)
app.command(
    "analysis.sharp.deliverables:main",
    name="extract",
    help="Build the campaign deliverables for one stamped run directory.",
)
app.command(
    "analysis.sharp.emit_sharp:main",
    name="sharp",
    help="Emit the ShARP deliverable CSVs from every solved archetype run in one run set.",
)
app.command(
    "analysis.dashboard.build:main",
    name="dashboard",
    help="Write dashboard.html into a run directory from its exports.",
)
