"""One command line for the campaign: ``uv run msm <command> [args]``.

Every command keeps its own logic and its own ``main``; this module only binds each
``main`` to a command name, so the team has one entry point instead of a set of script
paths. cyclopts derives each command's options from its ``main`` signature and its help
from the docstring, which is why no argument parsing lives here.

On the cluster's compute nodes, which have no internet, run it as
``uv run --no-sync msm <command>``.
"""

from cyclopts import App

from analysis.dashboard import build as dashboard
from analysis.hpc import launch, solve
from analysis.sharp import deliverables, emit_sharp

app = App(name="msm", help="ShARP electricity campaign command line.")

app.command(launch.main, name="launch")
app.command(solve.main, name="solve")
app.command(deliverables.main, name="extract")
app.command(emit_sharp.main, name="sharp")
app.command(dashboard.main, name="dashboard")
