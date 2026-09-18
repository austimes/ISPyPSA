"""One command line for the campaign: ``uv run isp <command> [args]``.

Every campaign script keeps its own logic and its own ``main``; this module only binds
each ``main`` to a command name, so the team has one entry point instead of nine script
paths. cyclopts derives each command's options from its ``main`` signature and its help
from the docstring, which is why no argument parsing lives here.

On the cluster's compute nodes, which have no internet, run it as
``uv run --no-sync isp <command>``.
"""

from cyclopts import App

from analysis.extension_campaign import (
    build_cost_dashboard,
    build_cost_dashboard_data,
    build_deliverables,
    build_manifest,
    build_trajectory_demand_dirs,
    hold_supply_curves,
    refresh,
)

app = App(name="isp", help="Extension campaign command line.")

# ponytail: every command module is imported eagerly, so `isp --help` pays the pypsa
# import. Swap to cyclopts lazy sub-apps if that start-up cost ever becomes annoying.
app.command(build_manifest.main, name="manifest")
app.command(build_trajectory_demand_dirs.main, name="tracedirs")
app.command(hold_supply_curves.main, name="hold-curves")
app.command(build_deliverables.main, name="deliverables")
app.command(build_cost_dashboard_data.main, name="cost-dashboard-data")
app.command(build_cost_dashboard.main, name="cost-dashboard")
app.command(refresh.main, name="refresh")
