from __future__ import annotations

from pathlib import Path

import pytest

from VmaxBuilder.config import (
    AllocationConfig,
    APIConfig,
    ConfigurationError,
    DiagnosticSeverity,
    KcatLevel,
    LoadingPolicy,
    LoadResolutionMode,
    ModelConfig,
    PrimaryOutputFormat,
    ProteinConfig,
    ProteinSourceMode,
    ReactionNotation,
    StageName,
    ValidationMode,
    ValidationPolicy,
    VmaxConfig,
    get_allowed_values,
    validate_allowed_value,
    validate_loading_policy,
    validate_model_config,
    validate_option_map,
)
from VmaxBuilder.config.options import OPTION_SPECS

# ruff: noqa: I001


def test_validation_policy_field_override_takes_precedence() -> None:
    policy = ValidationPolicy(
        mode=ValidationMode.STRICT,
        field_modes={"protein.tissue_type": ValidationMode.LENIENT},
        stage_modes={StageName.PROTEIN: ValidationMode.LENIENT},
    )

    assert policy.resolve_mode("protein.tissue_type") is ValidationMode.LENIENT
    assert policy.resolve_mode("protein.expression_scale") is ValidationMode.STRICT
    assert (
        policy.resolve_mode("protein.expression_scale", StageName.PROTEIN)
        is ValidationMode.LENIENT
    )


def test_validate_allowed_value_rejects_invalid_value_in_strict_mode() -> None:
    with pytest.raises(ConfigurationError):
        validate_allowed_value(
            "not-a-valid-value",
            field_name="protein.source_mode",
            allowed_values=("expression_ptr", "proteomics"),
            validation_mode=ValidationMode.STRICT,
        )


def test_validate_option_map_raises_on_unknown_option_in_strict_mode() -> None:
    policy = ValidationPolicy(mode=ValidationMode.STRICT)

    with pytest.raises(ConfigurationError):
        validate_option_map(
            {"unknown.option": 123},
            allowed_options=OPTION_SPECS,
            validation_policy=policy,
            stage_name=StageName.MODEL,
        )


def test_validate_option_map_allows_unknown_option_when_field_is_lenient() -> None:
    policy = ValidationPolicy(
        mode=ValidationMode.STRICT,
        field_modes={"custom.unknown": ValidationMode.LENIENT},
    )

    validated = validate_option_map(
        {"custom.unknown": 123},
        allowed_options=OPTION_SPECS,
        validation_policy=policy,
        stage_name=StageName.MODEL,
    )

    assert validated == {"custom.unknown": 123}


def test_api_config_stage_lookup_returns_stage_config() -> None:
    config = APIConfig(
        validation=ValidationPolicy(
            mode=ValidationMode.STRICT,
            halt_severity=DiagnosticSeverity.ERROR,
        ),
        loading=LoadingPolicy(
            resolution_mode=LoadResolutionMode.EXACT_THEN_DISCOVER,
            exact_paths={"model": Path("C:/data/model.json")},
        ),
        model=ModelConfig(),
        protein=ProteinConfig(source_mode=ProteinSourceMode.PROTEOMICS),
        allocation=AllocationConfig(trim_genes=False),
        vmax=VmaxConfig(kcat_level=KcatLevel.IFP_REACTION),
    )

    model_config = config.get_stage_config(StageName.MODEL)
    protein_config = config.get_stage_config(StageName.PROTEIN)
    allocation_config = config.get_stage_config(StageName.ALLOCATION)
    vmax_config = config.get_stage_config(StageName.VMAX)

    assert isinstance(model_config, ModelConfig)
    assert isinstance(protein_config, ProteinConfig)
    assert isinstance(allocation_config, AllocationConfig)
    assert isinstance(vmax_config, VmaxConfig)

    assert model_config.reaction_notation is ReactionNotation.STANDARD
    assert protein_config.source_mode is ProteinSourceMode.PROTEOMICS
    assert allocation_config.trim_genes is False
    assert vmax_config.kcat_level is KcatLevel.IFP_REACTION


def test_get_allowed_values_returns_catalogue_values() -> None:
    allowed_values = get_allowed_values("validation.mode")

    assert allowed_values == ("strict", "lenient")


def test_loading_policy_supports_direct_path_assignment() -> None:
    loading_policy = LoadingPolicy(
        exact_paths={"model": Path("C:/fallback/model_from_map.json")}
    )

    loading_policy.model_path = Path("C:/explicit/model.json")
    loading_policy.expression_path = Path("C:/explicit/expression.csv")

    effective_paths = loading_policy.get_effective_exact_paths()

    assert effective_paths["model"] == Path("C:/explicit/model.json")
    assert effective_paths["expression"] == Path("C:/explicit/expression.csv")


def test_loading_policy_supports_in_memory_model_assignment() -> None:
    model_object = object()
    loading_policy = LoadingPolicy(in_memory_inputs={"expression": object()})

    loading_policy.model_object = model_object
    effective_inputs = loading_policy.get_effective_in_memory_inputs()

    assert effective_inputs["model"] is model_object
    assert "expression" in effective_inputs


def test_loading_policy_get_output_directories_uses_output_path_and_results_dir() -> None:
    output_root = Path("C:/results")
    loading_policy = LoadingPolicy(
        output_path=output_root,
        results_dir_name="VmaxResults",
    )

    output_directories = loading_policy.get_output_directories()

    assert output_directories == (output_root, output_root / "VmaxResults")


def test_validate_model_config_accepts_known_values() -> None:
    validation_policy = ValidationPolicy(mode=ValidationMode.STRICT)
    model_config = ModelConfig(
        reaction_notation=ReactionNotation.STANDARD,
    )

    validated = validate_model_config(
        model_config,
        validation_policy=validation_policy,
    )

    assert validated["model.reaction_notation"] == "standard"


def test_validate_loading_policy_accepts_vmaxresults_and_feather() -> None:
    validation_policy = ValidationPolicy(mode=ValidationMode.STRICT)
    loading_policy = LoadingPolicy(
        resolution_mode=LoadResolutionMode.EXACT_THEN_DISCOVER,
        results_dir_name="VmaxResults",
        primary_output_format=PrimaryOutputFormat.FEATHER,
        write_additional_csv=True,
    )

    validated = validate_loading_policy(
        loading_policy,
        validation_policy=validation_policy,
    )

    assert validated["loading.results_dir_name"] == "VmaxResults"
    assert validated["loading.primary_output_format"] == "feather"
