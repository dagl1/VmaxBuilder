from __future__ import annotations

from pathlib import Path

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
)


@pytest.fixture
def full_config(tmp_path: Path) -> FullConfig:
    run_config = RunConfig(output_dir=tmp_path)
    return FullConfig(
        model=ImplementationConfig(),
        run=run_config,
        paths=run_config.paths,
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
    NECESSARY_OUTPUTS = [OutputSpec(name="required")]


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
        NECESSARY_OUTPUTS = [
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
