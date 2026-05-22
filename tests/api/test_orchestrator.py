from __future__ import annotations

from pathlib import Path

import pytest
from cobra import Metabolite, Model, Reaction
from cobra.io import save_json_model

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


def _make_simple_model() -> Model:
    model = Model("test_model")
    met_a = Metabolite("A")
    met_b = Metabolite("B")
    reaction = Reaction("r1")
    reaction.add_metabolites({met_a: -1.0, met_b: 1.0})
    reaction.bounds = (0.0, 10.0)
    model.add_reactions([reaction])
    return model


def _write_model_json(model_path: Path) -> None:
    model_path.parent.mkdir(parents=True, exist_ok=True)
    save_json_model(_make_simple_model(), str(model_path))


def test_run_model_uses_explicit_model_path(tmp_path: Path) -> None:
    model_path = tmp_path / "model.json"
    _write_model_json(model_path)
    config = APIConfig(
        validation=ValidationPolicy(mode=ValidationMode.STRICT),
        loading=LoadingPolicy(
            resolution_mode=LoadResolutionMode.EXACT_THEN_DISCOVER,
            model_path=model_path,
        ),
        model=ModelConfig(),
    )
    orchestrator = VmaxOrchestrator(config=config)

    scaffold = orchestrator.run_model()

    assert scaffold["artifacts"]["model_reference"]["source"] == "explicit_path"
    assert Path(scaffold["artifacts"]["model_reference"]["path"]) == model_path
    assert "reaction_notation" in scaffold["metadata"]["model_stage"]
    assert "model" in scaffold["artifacts"]


def test_build_default_api_config_returns_mutable_defaults() -> None:
    config = build_default_api_config()

    config.model.make_copy = False
    config.loading.model_path = Path("C:/data/model.json")

    assert config.model.make_copy is False
    assert config.loading.model_path == Path("C:/data/model.json")


def test_run_model_uses_discovery_roots_when_model_path_missing(tmp_path: Path) -> None:
    search_root = tmp_path / "search_root"
    model_path = search_root / "model_from_discovery.json"
    _write_model_json(model_path)
    config = APIConfig(
        validation=ValidationPolicy(mode=ValidationMode.STRICT),
        loading=LoadingPolicy(
            resolution_mode=LoadResolutionMode.EXACT_THEN_DISCOVER,
            search_roots=(search_root,),
        ),
    )
    orchestrator = VmaxOrchestrator(config=config)

    scaffold = orchestrator.run_model()

    assert scaffold["artifacts"]["model_reference"]["source"] == "discover"
    assert Path(scaffold["artifacts"]["model_reference"]["path"]) == model_path


def test_run_model_uses_in_memory_model_from_config() -> None:
    model_object = _make_simple_model()
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
    model_object = _make_simple_model()
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
    model_path = tmp_path / "model.json"
    _write_model_json(model_path)
    config = APIConfig(
        validation=ValidationPolicy(mode=ValidationMode.STRICT),
        loading=LoadingPolicy(
            model_path=model_path,
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


def test_run_executes_selected_stage_order(tmp_path: Path) -> None:
    model_path = tmp_path / "model.json"
    _write_model_json(model_path)
    config = APIConfig(
        validation=ValidationPolicy(mode=ValidationMode.STRICT),
        loading=LoadingPolicy(
            resolution_mode=LoadResolutionMode.EXACT_THEN_DISCOVER,
            model_path=model_path,
        ),
    )
    orchestrator = VmaxOrchestrator(config=config)

    scaffold = orchestrator.run(stages=(StageName.MODEL, StageName.PROTEIN))

    assert "model_stage" in scaffold["metadata"]
    assert "protein_stage" in scaffold["metadata"]
    assert scaffold["metadata"]["protein_stage"]["status"] == "placeholder_not_implemented"


def test_run_model_resolves_model_file_from_directory(tmp_path: Path) -> None:
    model_directory = tmp_path / "model_dir"
    model_path = model_directory / "Model_in_dir.json"
    _write_model_json(model_path)

    config = APIConfig(
        validation=ValidationPolicy(mode=ValidationMode.STRICT),
        loading=LoadingPolicy(model_path=model_directory),
    )
    orchestrator = VmaxOrchestrator(config=config)

    scaffold = orchestrator.run_model()

    assert scaffold["artifacts"]["model_reference"]["source"] == "explicit_path"
    assert Path(scaffold["artifacts"]["model_reference"]["path"]) == model_path
