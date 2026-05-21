from __future__ import annotations

from pathlib import Path

import pytest

from VmaxBuilder.api import VmaxOrchestrator, build_default_api_config
from VmaxBuilder.config import (
    APIConfig,
    ConfigurationError,
    LoadingPolicy,
    LoadResolutionMode,
    ModelConfig,
    StageName,
    ValidationMode,
    ValidationPolicy,
)

# ruff: noqa: I001


def test_run_model_uses_explicit_model_path() -> None:
    config = APIConfig(
        validation=ValidationPolicy(mode=ValidationMode.STRICT),
        loading=LoadingPolicy(
            resolution_mode=LoadResolutionMode.EXACT_THEN_DISCOVER,
            model_path=Path("C:/data/model.json"),
        ),
        model=ModelConfig(),
    )
    orchestrator = VmaxOrchestrator(config=config)

    scaffold = orchestrator.run_model()

    assert scaffold["artifacts"]["model_reference"]["source"] == "explicit_path"
    assert Path(scaffold["artifacts"]["model_reference"]["path"]) == Path(
        "C:/data/model.json"
    )
    assert "reaction_notation" in scaffold["metadata"]["model_stage"]


def test_build_default_api_config_returns_mutable_defaults() -> None:
    config = build_default_api_config()

    config.model.make_copy = False
    config.loading.model_path = Path("C:/data/model.json")

    assert config.model.make_copy is False
    assert config.loading.model_path == Path("C:/data/model.json")


def test_run_model_uses_discovery_roots_when_model_path_missing() -> None:
    config = APIConfig(
        validation=ValidationPolicy(mode=ValidationMode.STRICT),
        loading=LoadingPolicy(
            resolution_mode=LoadResolutionMode.EXACT_THEN_DISCOVER,
            search_roots=(Path("C:/data"), Path("C:/fallback")),
        ),
    )
    orchestrator = VmaxOrchestrator(config=config)

    scaffold = orchestrator.run_model()

    assert scaffold["artifacts"]["model_reference"]["source"] == "discover"
    assert [
        Path(path_value)
        for path_value in scaffold["artifacts"]["model_reference"]["search_roots"]
    ] == [Path("C:/data"), Path("C:/fallback")]


def test_run_model_uses_in_memory_model_from_config() -> None:
    model_object = object()
    config = APIConfig(
        validation=ValidationPolicy(mode=ValidationMode.STRICT),
        loading=LoadingPolicy(model_object=model_object),
    )
    orchestrator = VmaxOrchestrator(config=config)

    scaffold = orchestrator.run_model()

    assert scaffold["inputs"]["model"] is model_object
    assert scaffold["artifacts"]["model_reference"]["source"] == "in_memory"


def test_run_model_raises_when_no_resolution_inputs_configured() -> None:
    config = APIConfig(
        validation=ValidationPolicy(mode=ValidationMode.STRICT),
        loading=LoadingPolicy(resolution_mode=LoadResolutionMode.EXACT_THEN_DISCOVER),
    )
    orchestrator = VmaxOrchestrator(config=config)

    with pytest.raises(ConfigurationError):
        orchestrator.run_model()


def test_run_model_uses_in_memory_model_from_scaffold_input() -> None:
    model_object = object()
    config = APIConfig(
        validation=ValidationPolicy(mode=ValidationMode.STRICT),
        loading=LoadingPolicy(resolution_mode=LoadResolutionMode.EXACT_THEN_DISCOVER),
    )
    orchestrator = VmaxOrchestrator(config=config)

    scaffold = orchestrator.run_model(scaffold={"inputs": {"model": model_object}})

    assert scaffold["inputs"]["model"] is model_object
    assert scaffold["artifacts"]["model_reference"]["source"] == "in_memory"


def test_run_model_primes_output_directories_and_reprime_on_path_change(
    tmp_path: Path,
) -> None:
    first_output_dir = tmp_path / "out_a"
    second_output_dir = tmp_path / "out_b"
    config = APIConfig(
        validation=ValidationPolicy(mode=ValidationMode.STRICT),
        loading=LoadingPolicy(
            model_path=Path("C:/data/model.json"),
            output_path=first_output_dir,
        ),
    )
    orchestrator = VmaxOrchestrator(config=config)

    scaffold_first = orchestrator.run_model()

    assert first_output_dir.exists()
    assert (first_output_dir / config.loading.results_dir_name).exists()
    assert "orchestrator" in scaffold_first["metadata"]

    config.loading.output_path = second_output_dir
    scaffold_second = orchestrator.run_model()

    assert second_output_dir.exists()
    assert (second_output_dir / config.loading.results_dir_name).exists()
    assert "orchestrator" in scaffold_second["metadata"]


def test_run_executes_selected_stage_order() -> None:
    config = APIConfig(
        validation=ValidationPolicy(mode=ValidationMode.STRICT),
        loading=LoadingPolicy(
            resolution_mode=LoadResolutionMode.EXACT_THEN_DISCOVER,
            model_path=Path("C:/data/model.json"),
        ),
    )
    orchestrator = VmaxOrchestrator(config=config)

    scaffold = orchestrator.run(stages=(StageName.MODEL, StageName.PROTEIN))

    assert "model_stage" in scaffold["metadata"]
    assert "protein_stage" in scaffold["metadata"]
    assert scaffold["metadata"]["protein_stage"]["status"] == "placeholder_not_implemented"
