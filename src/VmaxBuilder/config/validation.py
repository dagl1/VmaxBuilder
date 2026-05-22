"""Generated: validation needed.

Description:
    Validation helpers for refactored VmaxBuilder configuration values.

"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict
from typing import Any

from VmaxBuilder.config.dataclasses import LoadingPolicy, ModelConfig, ValidationPolicy
from VmaxBuilder.config.enums import StageName, ValidationMode
from VmaxBuilder.config.options import OPTION_SPECS, OptionSpec


class ConfigurationError(ValueError):
    """Generated: validation needed.

    Description:
        Base configuration validation error.

    Args:
        message (str): Human-readable error message.
    """


class UnknownOptionError(ConfigurationError):
    """Generated: validation needed.

    Description:
        Error raised when config contains unsupported option keys in strict mode.

    Args:
        message (str): Human-readable error message.
    """


class InvalidOptionValueError(ConfigurationError):
    """Generated: validation needed.

    Description:
        Error raised when config option value is outside allowed values.

    Args:
        message (str): Human-readable error message.
    """


def resolve_validation_mode(
    policy: ValidationPolicy,
    field_name: str,
    stage_name: StageName | None = None,
) -> ValidationMode:
    """Generated: validation needed.

    Description:
        Resolve validation strictness for one field and optional stage context.

    Args:
        policy (ValidationPolicy): Validation policy to inspect.
        field_name (str): Canonical field name.
        stage_name (StageName | None): Optional stage name override context.

    Returns:
        ValidationMode: Resolved validation mode.
    """

    return policy.resolve_mode(field_name=field_name, stage_name=stage_name)


def validate_allowed_value(
    value: Any,
    *,
    field_name: str,
    allowed_values: Sequence[Any] | None,
    validation_mode: ValidationMode,
) -> Any:
    """Generated: validation needed.

    Description:
        Validate one value against a known allowed-value sequence.

    Args:
        value (Any): Candidate value to validate.
        field_name (str): Canonical field name.
        allowed_values (Sequence[Any] | None): Allowed values for the field.
        validation_mode (ValidationMode): Validation strictness to apply.

    Returns:
        Any: The original value when validation passes or lenient mode is active.

    Raises:
        InvalidOptionValueError: When value is not allowed in strict mode.
    """

    if allowed_values is None or validation_mode is ValidationMode.LENIENT:
        return value
    if value in allowed_values:
        return value
    allowed_values_text = ", ".join(repr(item) for item in allowed_values)
    raise InvalidOptionValueError(
        f"Invalid value for '{field_name}': {value!r}. Allowed values: {allowed_values_text}."
    )


def validate_option_map(
    options: Mapping[str, Any],
    *,
    allowed_options: Mapping[str, OptionSpec],
    validation_policy: ValidationPolicy,
    stage_name: StageName | None = None,
) -> dict[str, Any]:
    """Generated: validation needed.

    Description:
        Validate option mapping against option catalogue and policy.

    Args:
        options (Mapping[str, Any]): Config options to validate.
        allowed_options (Mapping[str, OptionSpec]): Allowed  catalogue.
        validation_policy (ValidationPolicy): Global and field-level validation policy.
        stage_name (StageName | None): Optional stage context for overrides.

    Returns:
        dict[str, Any]: Validated option copy.

    Raises:
        UnknownOptionError: When strict mode rejects unknown keys.
        InvalidOptionValueError: When strict mode rejects invalid values.
    """

    validated_options: dict[str, Any] = {}
    for option_name, option_value in options.items():
        option_spec = allowed_options.get(option_name)
        if option_spec is None:
            resolved_mode = resolve_validation_mode(
                validation_policy,
                option_name,
                stage_name,
            )
            if resolved_mode is ValidationMode.STRICT:
                raise UnknownOptionError(
                    f"Unknown option '{option_name}'. "
                    "Add it to config catalogue or set lenient mode."
                )
            validated_options[option_name] = option_value
            continue
        resolved_mode = resolve_validation_mode(validation_policy, option_name, stage_name)
        validated_options[option_name] = validate_allowed_value(
            option_value,
            field_name=option_name,
            allowed_values=option_spec.allowed_values,
            validation_mode=resolved_mode,
        )
    return validated_options


def config_as_plain_dict(config_object: Any) -> dict[str, Any]:
    """Generated: validation needed.

    Description:
        Convert dataclass config object into plain dictionary for inspection or serialization.

    Args:
        config_object (Any): Dataclass-based config object.

    Returns:
        dict[str, Any]: Serialized dictionary representation.

    Raises:
        TypeError: When input is not a dataclass instance.
    """

    try:
        return asdict(config_object)
    except TypeError as error:
        raise TypeError("config_object must be a dataclass instance") from error


def validate_model_config(
    model_config: ModelConfig,
    *,
    validation_policy: ValidationPolicy,
) -> dict[str, Any]:
    """Generated: validation needed.

    Description:
        Validate model-stage config fields against central allowed-value catalogue.

    Args:
        model_config (ModelConfig): Model-stage configuration to validate.
        validation_policy (ValidationPolicy): Validation strictness policy.

    Returns:
        dict[str, Any]: Validated model field map.

    Raises:
        UnknownOptionError: When model key is unknown in strict mode.
        InvalidOptionValueError: When model value is invalid in strict mode.
    """

    model_options: dict[str, Any] = {
        "model.reaction_notation": model_config.reaction_notation.value,
        "model.target_id_type": model_config.target_id_type,
    }
    return validate_option_map(
        model_options,
        allowed_options=OPTION_SPECS,
        validation_policy=validation_policy,
        stage_name=StageName.MODEL,
    )


def validate_loading_policy(
    loading_policy: LoadingPolicy,
    *,
    validation_policy: ValidationPolicy,
) -> dict[str, Any]:
    """Generated: validation needed.

    Description:
        Validate loading-policy fields that have explicit allowed-value catalogues.

    Args:
        loading_policy (LoadingPolicy): Loading policy object to validate.
        validation_policy (ValidationPolicy): Validation strictness policy.

    Returns:
        dict[str, Any]: Validated loading field map.

    Raises:
        UnknownOptionError: When loading key is unknown in strict mode.
        InvalidOptionValueError: When loading value is invalid in strict mode.
    """

    loading_options: dict[str, Any] = {
        "load.resolution_mode": loading_policy.resolution_mode.value,
        "loading.results_dir_name": loading_policy.results_dir_name,
        "loading.primary_output_format": loading_policy.primary_output_format.value,
        "loading.write_additional_csv": loading_policy.write_additional_csv,
    }
    return validate_option_map(
        loading_options,
        allowed_options=OPTION_SPECS,
        validation_policy=validation_policy,
    )
