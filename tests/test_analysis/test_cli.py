from analysis.cli import app


def test_app_registers_every_campaign_command():
    result = sorted(name for name in app if not name.startswith("-"))

    expected = sorted(["launch", "solve", "extract", "sharp", "dashboard"])
    assert result == expected
