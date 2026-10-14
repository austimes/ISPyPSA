from pathlib import Path
from unittest.mock import patch

import isp_workbook_parser
from isp_workbook_parser.config_model import load_yaml

from ispypsa.iasr_table_caching.local_cache import _build_required_tables


def test_v78_required_tables_ship_in_installed_parser():
    config_dir = (
        Path(isp_workbook_parser.__file__).parents[1] / "isp_table_configs" / "7.8"
    )
    shipped = {name for path in config_dir.glob("*.yaml") for name in load_yaml(path)}
    assert set(_build_required_tables()) - shipped == set()


def test_build_required_tables_new_format():
    with patch(
        "ispypsa.iasr_table_caching.local_cache.FEATURE_FLAGS",
        {"use_new_table_format": True},
    ):
        result = _build_required_tables()
    assert result == [
        "sub_regional_reference_nodes",
        "renewable_energy_zones",
        "flow_path_transfer_capability",
        "initial_transmission_limits",
    ]


def test_build_required_tables_old_format():
    with patch(
        "ispypsa.iasr_table_caching.local_cache.FEATURE_FLAGS",
        {"use_new_table_format": False},
    ):
        result = _build_required_tables()
    assert "sub_regional_reference_nodes" in result
    assert "initial_resource_limits" in result
    assert "existing_committed_anticipated_additional_generator_summary" in result
    assert "battery_properties" in result
    assert "vic_renewable_target" in result
    assert "build_costs" in result
    assert "expected_closure_years" in result
    assert (
        "maximum_capacity_existing_committed_anticipated_additional_generators"
        in result
    )
