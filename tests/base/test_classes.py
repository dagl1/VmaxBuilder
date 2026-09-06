from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from VmaxBuilder.base.classes import (
    BaseImplementation,
    BaseStage,
    fallback_provider,
    get_fallback_providers,
)
from VmaxBuilder.base.configs import (
    DiscoveredInput,
    FullConfig,
    ImplementationConfig,
    InputSpec,
    OutputSpec,
    RunConfig,
    Scaffold,
    TranscriptProcessingConfig,
)


@pytest.fixture
def full_config(tmp_path: Path) -> FullConfig:
    run_config = RunConfig(output_dir=tmp_path)
    return FullConfig(
        model=ImplementationConfig(),
        protein=ImplementationConfig(),
        allocation=ImplementationConfig(),
        Kcat=ImplementationConfig(),
        Vmax=ImplementationConfig(),
        run=run_config,
        paths=run_config.paths,
        transcripts=TranscriptProcessingConfig(),
    )


def _make_scaffold() -> Scaffold:
    return Scaffold(
        inputs={},
        artifacts={},
        outputs={},
        metadata={},
        diagnostics={},
        extras={},
        discovered_inputs={},
    )


class _DummyImplementation(BaseImplementation):
    STAGE_NAME = "model"
    IMPL_NAME = "dummy"

    def generate_outputs(self, scaffold: Scaffold) -> dict[str, int]:
        return {"generated": 1}


class _ChildImplementation(BaseImplementation):
    STAGE_NAME = "model"
    IMPL_NAME = "child"

    def generate_outputs(self, scaffold: Scaffold) -> dict[str, int]:
        return {"child_output": 2}


class _ParentImplementation(BaseImplementation):
    STAGE_NAME = "model"
    IMPL_NAME = "parent"
    CHILD_IMPLEMENTATIONS = [_ChildImplementation]

    def generate_outputs(self, scaffold: Scaffold) -> dict[str, int]:
        return {"unused": -1}


class _DummyStage(BaseStage):
    STAGE_NAME = "model"
    OUTPUTS = [OutputSpec(name="required")]


class _PruningStage(BaseStage):
    STAGE_NAME = "model"
    OUTPUTS = []


class _PruningMainImplementation(BaseImplementation):
    STAGE_NAME = "model"
    IMPL_NAME = "pruning-main"

    def generate_outputs(self, scaffold: Scaffold) -> dict[str, dict[str, Any]]:
        return {
            "outputs": {},
            "artifacts": {
                "needed_by_child": {"value": 1},
                "unused_after_main": {"value": 2},
            },
            "metadata": {},
            "diagnostics": {},
        }


class _PruningChildImplementation(BaseImplementation):
    STAGE_NAME = "model"
    IMPL_NAME = "pruning-child"
    INPUTS = [InputSpec(name="needed_by_child", in_scaffold=True)]

    def generate_outputs(self, scaffold: Scaffold) -> dict[str, dict[str, Any]]:
        assert scaffold.get_scaffold_value("needed_by_child") is not None
        return {
            "outputs": {},
            "artifacts": {"produced_by_child": {"value": 3}},
            "metadata": {},
            "diagnostics": {},
        }


class _PruningRootImplementation(BaseImplementation):
    STAGE_NAME = "model"
    IMPL_NAME = "pruning-root"
    CHILD_IMPLEMENTATIONS = [_PruningMainImplementation, _PruningChildImplementation]

    def generate_outputs(self, scaffold: Scaffold) -> dict[str, dict[str, Any]]:
        return {
            "outputs": {},
            "artifacts": {},
            "metadata": {},
            "diagnostics": {},
        }


class _AdditionalConsumerImplementation(BaseImplementation):
    STAGE_NAME = "model"
    IMPL_NAME = "additional-consumer"
    INPUTS = [InputSpec(name="needed_by_additional", in_scaffold=True)]

    def generate_outputs(self, scaffold: Scaffold) -> dict[str, dict[str, Any]]:
        assert scaffold.get_scaffold_value("needed_by_additional") is not None
        return {
            "outputs": {},
            "artifacts": {"produced_by_additional": {"value": 4}},
            "metadata": {},
            "diagnostics": {},
        }


class _MainProducerForAdditional(BaseImplementation):
    STAGE_NAME = "model"
    IMPL_NAME = "main-producer-for-additional"

    def generate_outputs(self, scaffold: Scaffold) -> dict[str, dict[str, Any]]:
        return {
            "outputs": {},
            "artifacts": {
                "needed_by_additional": {"value": 5},
                "unused_after_main": {"value": 6},
            },
            "metadata": {},
            "diagnostics": {},
        }


class _PruningWithAdditionalStage(BaseStage):
    STAGE_NAME = "model"
    OUTPUTS = []
    ADDITIONAL_IMPLEMENTATIONS = [_AdditionalConsumerImplementation]

    def run_additional_processes(self, scaffold: Scaffold) -> Scaffold:
        additional = self.additional_implementations["_AdditionalConsumerImplementation"]
        return additional.run(scaffold)


class _FutureAwareProducerImplementation(BaseImplementation):
    STAGE_NAME = "model"
    IMPL_NAME = "future-aware-producer"
    OUTPUTS = [
        OutputSpec(
            name="future_needed_key",
            data_type=dict,
            scaffold_location="artifacts",
            extension=".json",
        ),
        OutputSpec(
            name="local_unused_key",
            data_type=dict,
            scaffold_location="artifacts",
            extension=".json",
        ),
    ]

    def generate_outputs(self, scaffold: Scaffold) -> dict[str, dict[str, Any]]:
        return {
            "outputs": {},
            "artifacts": {
                "future_needed_key": {"value": 1},
                "local_unused_key": {"value": 2},
            },
            "metadata": {},
            "diagnostics": {},
        }


@pytest.mark.unit
def test_base_implementation_run_generates_outputs_when_no_children(
    full_config: FullConfig,
) -> None:
    implementation = _DummyImplementation(full_config)
    scaffold = _make_scaffold()

    updated_scaffold = implementation.run(scaffold)

    assert updated_scaffold.outputs["generated"] == 1


@pytest.mark.unit
def test_base_implementation_run_executes_child_implementations(
    full_config: FullConfig,
) -> None:
    implementation = _ParentImplementation(full_config)
    scaffold = _make_scaffold()

    updated_scaffold = implementation.run(scaffold)

    assert "child_output" in updated_scaffold.outputs
    assert "unused" not in updated_scaffold.outputs


@pytest.mark.unit
def test_base_stage_ensure_outputs_accepts_outputs_and_inputs(
    full_config: FullConfig,
) -> None:
    implementation = _DummyImplementation(full_config)
    stage = _DummyStage(implementation=implementation, config=full_config)
    scaffold = _make_scaffold()
    scaffold.inputs["required"] = "value"

    stage.ensure_outputs(scaffold)


@pytest.mark.unit
def test_base_stage_ensure_outputs_raises_for_missing_output(
    full_config: FullConfig,
) -> None:
    implementation = _DummyImplementation(full_config)
    stage = _DummyStage(implementation=implementation, config=full_config)
    scaffold = _make_scaffold()

    with pytest.raises(ValueError, match="Necessary output 'required' is missing"):
        stage.ensure_outputs(scaffold)


@pytest.mark.unit
def test_base_stage_ensure_outputs_runs_validator(full_config: FullConfig) -> None:
    class _ValidatedStage(BaseStage):
        OUTPUTS = [
            OutputSpec(
                name="required",
                validator=lambda value: (value == 10, "must equal 10"),
            )
        ]

    implementation = _DummyImplementation(full_config)
    stage = _ValidatedStage(implementation=implementation, config=full_config)
    scaffold = _make_scaffold()
    scaffold.outputs["required"] = 9

    with pytest.raises(ValueError, match="Validation failed"):
        stage.ensure_outputs(scaffold)


@pytest.mark.unit
def test_load_inputs_loads_discovered_input(full_config: FullConfig, tmp_path: Path) -> None:
    file_path = tmp_path / "input.txt"
    file_path.write_text("demo", encoding="utf-8")

    class _LoaderImplementation(BaseImplementation):
        STAGE_NAME = "model"
        IMPL_NAME = "loader"
        INPUTS = [
            InputSpec(
                name="loaded",
                loader=lambda path, suffix="": f"{Path(path).name}{suffix}",
                loader_args={"suffix": "_ok"},
            )
        ]

        def generate_outputs(self, scaffold: Scaffold) -> dict[str, int]:
            return {}

    implementation = _LoaderImplementation(full_config)
    scaffold = _make_scaffold()
    scaffold.discovered_inputs = {
        "model": {
            "loaded": DiscoveredInput(
                input_name="loaded",
                file_path=file_path,
                exists=True,
                source="explicit_file_path",
            )
        }
    }

    implementation.load_inputs(scaffold)

    assert scaffold.inputs["loaded"] == "input.txt_ok"


@pytest.mark.unit
def test_load_inputs_raises_for_missing_required_input(full_config: FullConfig) -> None:
    class _LoaderImplementation(BaseImplementation):
        STAGE_NAME = "model"
        IMPL_NAME = "loader"
        INPUTS = [InputSpec(name="missing", loader=None, optional=False)]

        def generate_outputs(self, scaffold: Scaffold) -> dict[str, int]:
            return {}

    implementation = _LoaderImplementation(full_config)
    scaffold = _make_scaffold()
    scaffold.discovered_inputs = {"model": {}}

    with pytest.raises(ValueError, match="Cannot load input 'missing'"):
        implementation.load_inputs(scaffold)


@pytest.mark.unit
def test_validate_input_falls_back_to_outputs(full_config: FullConfig) -> None:
    implementation = _DummyImplementation(full_config)
    scaffold = _make_scaffold()
    scaffold.outputs["fallback"] = 5
    input_spec = InputSpec(name="fallback", validator=lambda value: (value == 5, "ok"))

    updated_scaffold, result = implementation.validate_input(scaffold, input_spec)

    assert updated_scaffold.outputs["fallback"] == 5
    assert result == {"is_valid": True, "return_message": "ok"}


@pytest.mark.unit
def test_validate_input_removes_optional_invalid_input(full_config: FullConfig) -> None:
    implementation = _DummyImplementation(full_config)
    scaffold = _make_scaffold()
    scaffold.inputs["optional_key"] = "bad"
    input_spec = InputSpec(
        name="optional_key",
        optional=True,
        validator=lambda value: (False, f"invalid:{value}"),
    )

    updated_scaffold, result = implementation.validate_input(scaffold, input_spec)

    assert "optional_key" not in updated_scaffold.inputs
    assert result == {"is_valid": False, "return_message": "invalid:bad"}


@pytest.mark.unit
def test_validate_inputs_aggregates_results(full_config: FullConfig) -> None:
    class _ValidationImplementation(BaseImplementation):
        STAGE_NAME = "model"
        IMPL_NAME = "validator"
        INPUTS = [
            InputSpec(name="first", validator=lambda value: (value == 1, "first")),
            InputSpec(name="second", validator=lambda value: (value == 2, "second")),
        ]

        def generate_outputs(self, scaffold: Scaffold) -> dict[str, int]:
            return {}

    implementation = _ValidationImplementation(full_config)
    scaffold = _make_scaffold()
    scaffold.inputs["first"] = 1
    scaffold.inputs["second"] = 2

    _, results = implementation.validate_inputs(scaffold)

    assert len(results) == 2
    assert {result["input_name"] for result in results} == {"first", "second"}


@pytest.mark.unit
def test_fallback_provider_registers_metadata() -> None:
    class _Providers:
        @fallback_provider(provides="x", requires={"a", "b"})
        def provide_x(self) -> str:
            return "x"

        def helper(self) -> str:
            return "helper"

    providers = get_fallback_providers(_Providers)

    assert "x" in providers
    assert providers["x"].provides == "x"
    assert providers["x"].requires == frozenset({"a", "b"})


@pytest.mark.unit
def test_scaffold_pruning_keeps_keys_needed_by_remaining_children(
    full_config: FullConfig,
) -> None:
    full_config.run.prune_scaffold_unused_objects = True
    implementation = _PruningRootImplementation(full_config)
    stage = _PruningStage(implementation=implementation, config=full_config)
    scaffold = _make_scaffold()
    scaffold.extras["_orchestrator_full_run_active"] = True

    updated_scaffold = stage.run(scaffold)

    assert "needed_by_child" not in updated_scaffold.artifacts
    assert "unused_after_main" not in updated_scaffold.artifacts
    assert "produced_by_child" not in updated_scaffold.artifacts


@pytest.mark.unit
def test_scaffold_pruning_accounts_for_additional_implementations(
    full_config: FullConfig,
) -> None:
    full_config.run.prune_scaffold_unused_objects = True
    implementation = _MainProducerForAdditional(full_config)
    stage = _PruningWithAdditionalStage(implementation=implementation, config=full_config)
    scaffold = _make_scaffold()
    scaffold.extras["_orchestrator_full_run_active"] = True

    updated_scaffold = stage.run(scaffold)

    assert "needed_by_additional" not in updated_scaffold.artifacts
    assert "unused_after_main" not in updated_scaffold.artifacts
    assert "produced_by_additional" not in updated_scaffold.artifacts


@pytest.mark.unit
def test_stage_only_run_does_not_prune_scaffold(
    full_config: FullConfig,
) -> None:
    full_config.run.prune_scaffold_unused_objects = True
    implementation = _PruningRootImplementation(full_config)
    stage = _PruningStage(implementation=implementation, config=full_config)
    scaffold = _make_scaffold()

    updated_scaffold = stage.run(scaffold)

    model_stage_artifacts = updated_scaffold.artifacts.get("model_stage", {})
    assert "needed_by_child" in model_stage_artifacts
    assert "unused_after_main" in model_stage_artifacts
    assert "produced_by_child" in model_stage_artifacts


@pytest.mark.unit
def test_reuse_existing_results_skips_implementation_when_files_exist(
    full_config: FullConfig,
) -> None:
    class _ReuseExistingOutputsImplementation(BaseImplementation):
        STAGE_NAME = "model"
        IMPL_NAME = "reuse-existing"
        OUTPUTS = [
            OutputSpec(
                name="cached_output",
                data_type=dict,
                scaffold_location="outputs",
                extension=".json",
            )
        ]

        def __init__(self, cfg: FullConfig):
            super().__init__(cfg)
            self.generate_calls = 0

        def generate_outputs(self, scaffold: Scaffold) -> dict[str, dict[str, Any]]:
            self.generate_calls += 1
            return {
                "outputs": {"cached_output": {"source": "generated"}},
                "artifacts": {},
                "metadata": {},
                "diagnostics": {},
            }

    full_config.run.use_existing_results_if_available = True
    full_config.run.paths.outputs_dir.mkdir(parents=True, exist_ok=True)
    cached_output_path = full_config.run.paths.outputs_dir / "cached_output.json"
    with cached_output_path.open("w", encoding="utf-8") as f:
        json.dump({"source": "disk"}, f)

    implementation = _ReuseExistingOutputsImplementation(full_config)
    stage = _PruningStage(implementation=implementation, config=full_config)
    scaffold = _make_scaffold()

    updated_scaffold = stage.run(scaffold)

    assert implementation.generate_calls == 0
    assert updated_scaffold.outputs["cached_output"]["source"] == "disk"


@pytest.mark.unit
def test_reuse_existing_results_runs_implementation_when_file_missing(
    full_config: FullConfig,
) -> None:
    class _ReuseExistingOutputsImplementation(BaseImplementation):
        STAGE_NAME = "model"
        IMPL_NAME = "reuse-existing-missing"
        OUTPUTS = [
            OutputSpec(
                name="cached_output",
                data_type=dict,
                scaffold_location="outputs",
                extension=".json",
            )
        ]

        def __init__(self, cfg: FullConfig):
            super().__init__(cfg)
            self.generate_calls = 0

        def generate_outputs(self, scaffold: Scaffold) -> dict[str, dict[str, Any]]:
            self.generate_calls += 1
            return {
                "outputs": {"cached_output": {"source": "generated"}},
                "artifacts": {},
                "metadata": {},
                "diagnostics": {},
            }

    full_config.run.use_existing_results_if_available = True
    implementation = _ReuseExistingOutputsImplementation(full_config)
    stage = _PruningStage(implementation=implementation, config=full_config)
    scaffold = _make_scaffold()

    updated_scaffold = stage.run(scaffold)

    assert implementation.generate_calls == 1
    assert updated_scaffold.outputs["cached_output"]["source"] == "generated"


@pytest.mark.unit
def test_scaffold_pruning_keeps_keys_needed_by_future_stages(
    full_config: FullConfig,
) -> None:
    full_config.run.prune_scaffold_unused_objects = True
    implementation = _FutureAwareProducerImplementation(full_config)
    stage = _PruningStage(implementation=implementation, config=full_config)
    scaffold = _make_scaffold()
    scaffold.extras["_orchestrator_full_run_active"] = True
    scaffold.extras["_orchestrator_future_required_input_names"] = {"future_needed_key"}

    updated_scaffold = stage.run(scaffold)

    model_stage_artifacts = updated_scaffold.artifacts.get("model_stage", {})
    assert "future_needed_key" in model_stage_artifacts
    assert "local_unused_key" not in model_stage_artifacts


@pytest.mark.unit
def test_reusable_output_specs_include_future_stage_dependencies(
    full_config: FullConfig,
) -> None:
    implementation = _FutureAwareProducerImplementation(full_config)
    scaffold = _make_scaffold()
    scaffold.extras["_orchestrator_future_required_input_names"] = ["future_needed_key"]

    reusable_specs = implementation._get_reusable_output_specs(scaffold)

    reusable_names = {spec.name for spec in reusable_specs}
    assert "future_needed_key" in reusable_names
    assert "local_unused_key" not in reusable_names
