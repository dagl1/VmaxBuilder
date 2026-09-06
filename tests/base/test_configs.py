from __future__ import annotations

from pathlib import Path

import pytest

from VmaxBuilder.base.configs import RunConfig, Scaffold


@pytest.mark.unit
def test_run_config_sets_expected_paths(tmp_path: Path) -> None:
    config = RunConfig(output_dir=tmp_path, run_name="demo")

    assert config.paths.results_dir == tmp_path.resolve() / "demo"
    assert config.paths.diagnostics_dir == tmp_path.resolve() / "demo" / "diagnostics"
    assert config.paths.outputs_dir == tmp_path.resolve() / "demo" / "outputs"


@pytest.mark.unit
def test_run_config_resyncs_paths_when_run_name_changes(tmp_path: Path) -> None:
    config = RunConfig(output_dir=tmp_path, run_name="before")

    config.run_name = "after"

    assert config.paths.results_dir == tmp_path.resolve() / "after"


@pytest.mark.unit
def test_run_config_resyncs_paths_when_output_dir_changes(tmp_path: Path) -> None:
    config = RunConfig(output_dir=tmp_path / "first", run_name="demo")

    config.output_dir = tmp_path / "second"

    assert config.paths.results_dir == (tmp_path / "second").resolve() / "demo"


@pytest.mark.unit
def test_run_config_print_level_read_only_after_init(tmp_path: Path) -> None:
    config = RunConfig(output_dir=tmp_path)

    with pytest.raises(AttributeError, match="print_level is read-only"):
        config.print_level = "DEBUG"


@pytest.mark.unit
def test_scaffold_get_scaffold_location_uses_priority_order() -> None:
    scaffold = Scaffold(
        inputs={"shared": "in"},
        artifacts={},
        outputs={"shared": "out"},
        metadata={},
        diagnostics={},
        extras={},
        discovered_inputs={},
    )

    location = scaffold.get_scaffold_location("shared")

    assert location == "inputs"


@pytest.mark.unit
def test_scaffold_get_scaffold_location_returns_none_for_missing_key() -> None:
    scaffold = Scaffold(
        inputs={},
        artifacts={},
        outputs={},
        metadata={},
        diagnostics={},
        extras={},
        discovered_inputs={},
    )

    location = scaffold.get_scaffold_location("missing")

    assert location is None


@pytest.mark.unit
def test_scaffold_update_scaffold_updates_existing_key_location() -> None:
    scaffold = Scaffold(
        inputs={"existing": 1},
        artifacts={},
        outputs={},
        metadata={},
        diagnostics={},
        extras={},
        discovered_inputs={},
    )

    scaffold.update_scaffold({"existing": 2})

    assert scaffold.inputs["existing"] == 2
    assert "existing" not in scaffold.outputs


@pytest.mark.unit
def test_scaffold_update_scaffold_adds_new_key_to_outputs() -> None:
    scaffold = Scaffold(
        inputs={},
        artifacts={},
        outputs={},
        metadata={},
        diagnostics={},
        extras={},
        discovered_inputs={},
    )

    scaffold.update_scaffold({"new_output": 123})

    assert scaffold.outputs["new_output"] == 123


@pytest.mark.unit
def test_scaffold_update_scaffold_updates_outputs_when_key_exists_only_in_outputs() -> None:
    scaffold = Scaffold(
        inputs={},
        artifacts={},
        outputs={"existing_out": 10},
        metadata={},
        diagnostics={},
        extras={},
        discovered_inputs={},
    )

    scaffold.update_scaffold({"existing_out": 20})

    assert scaffold.outputs["existing_out"] == 20
