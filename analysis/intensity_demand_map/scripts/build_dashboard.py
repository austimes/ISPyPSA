"""Render the map dashboard: inline dashboard_data.json into the template.

Same mechanism as the previous sweep's dashboards: the page is published as a
single self-contained file with no network access, so the data is inlined at
the marker rather than fetched.

Usage:
    uv run python analysis/intensity_demand_map/scripts/build_dashboard.py
"""

from pathlib import Path

OUT = Path("analysis/intensity_demand_map")
MARKER = "/*__MAP_DATA__*/null"


def main() -> None:
    blob = (OUT / "dashboard_data.json").read_text(encoding="utf-8")
    template = (OUT / "dashboard_template.html").read_text(encoding="utf-8")
    assert MARKER in template, "data marker missing from dashboard_template.html"
    rendered = OUT / "dashboard.html"
    rendered.write_text(template.replace(MARKER, blob), encoding="utf-8")
    print(f"wrote {rendered}  ({rendered.stat().st_size / 1024:.1f} KiB)")


if __name__ == "__main__":
    main()
