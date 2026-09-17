"""Render the campaign dashboard by injecting collected run data into the page template.

Keeps the page self-contained so it can be published or opened from a file with no server
and no second request. Re-run after `build_dashboard_data.py` to refresh the page.

Usage:
    uv run python analysis/extension_campaign/build_dashboard.py \\
        --data outputs/campaign/dashboard_data.json --out outputs/campaign/dashboard.html
"""

import argparse
import json
from pathlib import Path

_PLACEHOLDER = "__DASHBOARD_DATA__"
_TEMPLATE = Path(__file__).parent / "dashboard_template.html"


def render(template: str, data: dict) -> str:
    """Inline the run data into the template as a JavaScript object literal.

    JSON is valid JavaScript, so the payload drops straight into `const DATA = ...;`. The one
    sequence that could end the enclosing script tag early is a closing tag inside a string,
    so its slash is escaped, which JavaScript reads back as the same character.
    """
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    return template.replace(_PLACEHOLDER, payload)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data", type=Path, default=Path("outputs/campaign/dashboard_data.json")
    )
    parser.add_argument(
        "--out", type=Path, default=Path("outputs/campaign/dashboard.html")
    )
    args = parser.parse_args()

    data = json.loads(args.data.read_text())
    page = render(_TEMPLATE.read_text(encoding="utf-8"), data)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(page, encoding="utf-8")
    print(
        f"{args.out} ({len(page) / 1024:.0f} KB) "
        f"from {data['chains_found']} chains, {data['milestones_solved']} milestones"
    )


if __name__ == "__main__":
    main()
