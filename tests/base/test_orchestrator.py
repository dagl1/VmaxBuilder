from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from VmaxBuilder.base.classes import BaseImplementation
from VmaxBuilder.base.configs import (
    FullConfig,
    ImplementationConfig,
    InputSpec,
    RunConfig,
    StageLoadingInfo,
)
from VmaxBuilder.base.exceptions import ImplementationConfigConflictError
from VmaxBuilder.base.orchestrator import Orchestrator
from VmaxBuilder.utils.custom_logging import CustomLogger


class _DemoImplementation(BaseImplementation):
    STAGE_NAME = "model"
    IMPL_NAME = "demo"

    def generate_outputs(self, scaffold: Any) -> dict[str, Any]:
        return {}


def _make_orchestrator_stub(tmp_path: Path) -> Orchestrator:
    orchestrator = object.__new__(Orchestrator)
    orchestrator.logger = CustomLogger("orchestrator-test", tmp_path, auto_parse=False)
    run_config = RunConfig(output_dir=tmp_path, run_name="orchestrator")
    orchestrator.config = FullConfig(
        model=ImplementationConfig(),
        run=run_config,
        paths=run_config.paths,
    )
    orchestrator.registry = {}
    return orchestrator


@pytest.mark.unit
def test_initialise_scaffold_creates_empty_structure() -> None:
    scaffold = Orchestrator._initialise_scaffold()

    assert scaffold.inputs == {}
    assert scaffold.outputs == {}
    assert scaffold.discovered_inputs == {}


@pytest.mark.unit
def test_initialise_scaffold_rejects_non_none_input() -> None:
    existing_scaffold = Orchestrator._initialise_scaffold()

    with pytest.raises(ValueError, match="Scaffold must be None"):
        Orchestrator._initialise_scaffold(scaffold=existing_scaffold)


@pytest.mark.unit
def test_set_print_level_accepts_string_and_updates_config(tmp_path: Path) -> None:
    orchestrator = _make_orchestrator_stub(tmp_path)

    orchestrator.set_print_level("debug")

    assert orchestrator.logger.print_level == 4
    assert orchestrator.config.run._print_level == "DEBUG"


@pytest.mark.unit
def test_set_print_level_accepts_integer(tmp_path: Path) -> None:
    orchestrator = _make_orchestrator_stub(tmp_path)

    orchestrator.set_print_level(2)

    assert orchestrator.logger.print_level == 2
    assert orchestrator.config.run._print_level == "WARNING"


@pytest.mark.unit
def test_set_print_level_rejects_invalid_value(tmp_path: Path) -> None:
    orchestrator = _make_orchestrator_stub(tmp_path)

    with pytest.raises(ValueError, match="Invalid print level"):
        orchestrator.set_print_level("loud")


@pytest.mark.unit
def test_resolve_implementation_returns_registered_entry(tmp_path: Path) -> None:
    orchestrator = _make_orchestrator_stub(tmp_path)
    orchestrator.registry = {"model:demo": _DemoImplementation}

    resolved = orchestrator._resolve_implementation("model", "demo")

    assert resolved is _DemoImplementation


@pytest.mark.unit
def test_resolve_implementation_raises_for_missing_entry(tmp_path: Path) -> None:
    orchestrator = _make_orchestrator_stub(tmp_path)
    orchestrator.registry = {}

    with pytest.raises(
        ValueError, match="Implementation 'missing' for stage 'model' not found"
    ):
        orchestrator._resolve_implementation("model", "missing")


@pytest.mark.unit
def test_normalize_directories_handles_none_string_and_list(tmp_path: Path) -> None:
    orchestrator = _make_orchestrator_stub(tmp_path)

    assert orchestrator._normalize_directories(None) == []
    single = orchestrator._normalize_directories(str(tmp_path))
    multiple = orchestrator._normalize_directories([tmp_path, str(tmp_path / "child")])

    assert single == [tmp_path.resolve()]
    assert multiple[0] == tmp_path.resolve()
    assert multiple[1] == (tmp_path / "child").resolve()


@pytest.mark.unit
def test_resolve_explicit_file_path_returns_existing_path(tmp_path: Path) -> None:
    orchestrator = _make_orchestrator_stub(tmp_path)
    file_path = tmp_path / "demo.csv"
    file_path.write_text("x", encoding="utf-8")
    input_spec = InputSpec(name="demo")
    loading_info = StageLoadingInfo(stage_name="model", file_paths={"demo": file_path})

    resolved = orchestrator._resolve_explicit_file_path(input_spec, loading_info)

    assert resolved == file_path.resolve()


@pytest.mark.unit
def test_select_match_uses_extension_priority(tmp_path: Path) -> None:
    orchestrator = _make_orchestrator_stub(tmp_path)
    first = tmp_path / "input.csv"
    second = tmp_path / "input.tsv"
    input_spec = InputSpec(name="data", extensions=[".tsv", ".csv"])

    selected = orchestrator._select_match([first, second], input_spec)

    assert selected == second


@pytest.mark.unit
def test_select_match_returns_none_for_empty_matches(tmp_path: Path) -> None:
    orchestrator = _make_orchestrator_stub(tmp_path)
    input_spec = InputSpec(name="data", extensions=[".csv"])

    selected = orchestrator._select_match([], input_spec)

    assert selected is None


@pytest.mark.unit
def test_find_matching_files_requires_prefix_and_extensions(tmp_path: Path) -> None:
    orchestrator = _make_orchestrator_stub(tmp_path)
    sample = tmp_path / "gene_input.csv"
    sample.write_text("x", encoding="utf-8")

    missing_specs = InputSpec(name="a", prefix=None, extensions=[".csv"])
    empty = orchestrator._find_matching_files(tmp_path, missing_specs)
    assert empty == []

    valid_specs = InputSpec(name="b", prefix="gene_", extensions=[".csv"])
    found = orchestrator._find_matching_files(tmp_path, valid_specs)
    assert found == [sample]


@pytest.mark.unit
def test_validate_config_conflicts_rejects_non_dataclass(tmp_path: Path) -> None:
    orchestrator = _make_orchestrator_stub(tmp_path)

    class _NotDataclass:
        value: int = 1

    with pytest.raises(TypeError, match="is not a dataclass"):
        orchestrator._validate_config_conflicts([_NotDataclass])


@pytest.mark.unit
def test_validate_config_conflicts_detects_duplicate_field(tmp_path: Path) -> None:
    orchestrator = _make_orchestrator_stub(tmp_path)

    @dataclass
    class _A:
        shared: int = 1

    @dataclass
    class _B:
        shared: int = 2

    with pytest.raises(ImplementationConfigConflictError, match="Configuration key 'shared'"):
        orchestrator._validate_config_conflicts([_A, _B])


@pytest.mark.unit
def test_build_flattened_config_combines_dataclass_fields(tmp_path: Path) -> None:
    orchestrator = _make_orchestrator_stub(tmp_path)

    @dataclass
    class _A:
        alpha: int = 1

    @dataclass
    class _B:
        beta: str = "x"

    combined = orchestrator._build_flattened_config([_A, _B])
    config = combined()

    assert isinstance(config, ImplementationConfig)
    assert config.alpha == 1
    assert config.beta == "x"
