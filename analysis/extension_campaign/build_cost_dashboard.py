"""Render the campaign cost dashboard by injecting its data into the page template.

Keeps the page self-contained so it can be published or opened from a file with no
server and no second request. Re-run after `build_cost_dashboard_data.py` to refresh
the page.

Usage:
    uv run python analysis/extension_campaign/build_cost_dashboard.py \\
        --data outputs/exports/cost_dashboard_data.json \\
        --out outputs/exports/cost_dashboard.html
"""

import argparse
import json
from pathlib import Path

_PLACEHOLDER = "__DASHBOARD_DATA__"
_TEMPLATE = Path(__file__).parent / "cost_dashboard_template.html"
_EXPORTS = Path("outputs/exports")


def render(template: str, data: dict) -> str:
    """Inline the campaign data into the template as a JavaScript object literal.

    JSON is valid JavaScript, so the payload drops straight into `const DATA = ...;`. The
    one sequence that could end the enclosing script tag early is a closing tag inside a
    string, so its slash is escaped, which JavaScript reads back as the same character.
    """
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    return template.replace(_PLACEHOLDER, payload)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data", type=Path, default=_EXPORTS / "cost_dashboard_data.json"
    )
    parser.add_argument("--out", type=Path, default=_EXPORTS / "cost_dashboard.html")
    args = parser.parse_args()

    data = json.loads(args.data.read_text(encoding="utf-8"))
    page = render(_TEMPLATE.read_text(encoding="utf-8"), data)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(page, encoding="utf-8")
    print(
        f"{args.out} ({len(page) / 1024:.0f} KB) from {data['meta']['chains']} chains, "
        f"{len(data['cells'])} milestones"
    )


if __name__ == "__main__":
    main()
