from __future__ import annotations

import inspect
from collections import defaultdict
from dataclasses import fields, is_dataclass, make_dataclass
from typing import TYPE_CHECKING, Any, Iterator, Protocol

from VmaxBuilder.base.configs import ImplementationConfig
from VmaxBuilder.base.exceptions import ImplementationConfigConflictError
from VmaxBuilder.stages.model.model import ModelCoreConfig, ModelStage
from VmaxBuilder.utils.stubs import _update_stub_for_implementation

if TYPE_CHECKING:
    from VmaxBuilder.base.classes import BaseImplementation

# ============================================================
# Registry Models
# ============================================================
IMPLEMENTATION_REGISTRY: dict[str, type["BaseImplementation"]] = {}

STAGE_IMPLEMENTATIONS: defaultdict[str, list[str]] = defaultdict(list)
STAGE_CORE_CONFIGS: dict[str, type] = {
    "model": ModelCoreConfig,
}


def register_implementation(stage: str, name: str):
    """Generated: validation needed.

    Description:
        Register implementation class under stage and name lookup keys.

    Args:
        stage (str): Stage namespace.
        name (str): Implementation identifier within stage.

    Returns:
        Callable[[type], type]: Decorator that registers class and injects metadata.
    """

    def decorator(cls):
        key = f"{stage}:{name}"
        IMPLEMENTATION_REGISTRY[key] = cls

        STAGE_IMPLEMENTATIONS.setdefault(stage, []).append(name)

        cls.STAGE_NAME = stage
        cls.IMPL_NAME = name

        print(
            f"Registered implementation '{name}' for stage '{stage}' "
            f"with config class '{cls._RESOLVED_CONFIG_CLASS.__name__}'"
            " and core config class "
            f" config options are: {[f.name for f in fields(cls._RESOLVED_CONFIG_CLASS)]}"
        )

        _update_stub_for_implementation(
            stage=stage, name=name, config_cls=cls._RESOLVED_CONFIG_CLASS
        )

        return cls

    return decorator


# todo: move to utils and remove from orchestrator
def _iter_implementations(
    implementation: type[BaseImplementation] | BaseImplementation,
) -> Iterator[BaseImplementation | type[BaseImplementation]]:
    yield implementation

    child_implementations: list[BaseImplementation] = getattr(
        implementation, "child_implementations", []
    )

    for child_implementation in child_implementations:
        yield from _iter_implementations(child_implementation)


def validate_config_conflicts(
    config_classes: list[type],
):
    # todo: move to utils and remove from here and orchestrator
    key_owners = {}
    for config_cls in config_classes:
        source_file = inspect.getfile(config_cls)
        _, line_number = inspect.getsourcelines(config_cls)
        if not is_dataclass(config_cls):
            raise TypeError(
                f"Config class '{config_cls.__name__}' in {source_file} is not a dataclass."
            )

        for _field in fields(config_cls):
            if _field.name in key_owners:
                previous = key_owners[_field.name]
                if not isinstance(previous["config"], type) or not isinstance(
                    config_cls, type
                ):
                    raise ValueError(
                        f"Conflict detected for config key '{_field.name}' between "
                        f"{previous['config']} and {config_cls},"
                        "but one of them is not a class."
                    )

                raise ImplementationConfigConflictError(
                    key=_field.name,
                    config_a=previous["config"],
                    config_b=config_cls,
                    file_a=f"{previous['file']}:{previous['line']}",
                    file_b=f"{source_file}:{line_number}",
                )

            key_owners[_field.name] = {
                "config": config_cls,
                "file": source_file,
                "line": line_number,
            }


def resolve_implementation_config_class(
    impl_cls: type["BaseImplementation"],
    core_config_cls: type | None = None,
) -> type:
    stage_configs = []

    for impl in _iter_implementations(impl_cls):
        config_cls = getattr(impl, "CONFIG_CLASS", None)
        if config_cls is not None:
            stage_configs.append(config_cls)

    if core_config_cls is not None:
        stage_configs.append(core_config_cls)

    validate_config_conflicts(stage_configs)

    return build_flattened_config(stage_configs)


def build_flattened_config(config_classes: list[type]) -> type:
    # todo: move to utils and remove from here and orchestrator
    combined_fields = []

    for config_cls in config_classes:
        for _field in fields(config_cls):
            combined_fields.append(
                (
                    _field.name,
                    _field.type,
                    _field,
                )
            )

    return make_dataclass(
        cls_name="CombinedConfig",
        fields=combined_fields,
        bases=(ImplementationConfig,),
        slots=True,
    )


def get_available_stages() -> list[str]:
    """Generated: validation needed.

    Description:
        Return sorted unique stage names currently present in registry.

    Returns:
        list[str]: Sorted stage names.
    """
    stages = set()
    for key in IMPLEMENTATION_REGISTRY.keys():
        stage, _ = key.split(":")
        stages.add(stage)
    return sorted(stages)


def get_available_implementations(stage: str) -> list[str]:
    """Generated: validation needed.

    Description:
        Return sorted implementation names for given stage.

    Args:
        stage (str): Stage namespace.

    Returns:
        list[str]: Sorted implementation names for stage.
    """
    implementations = []
    for key in IMPLEMENTATION_REGISTRY.keys():
        s, name = key.split(":")
        if s == stage:
            implementations.append(name)
    return sorted(implementations)


def get_implementation_info(stage: str, name: str) -> dict[str, Any]:
    """Generated: validation needed.

    Description:
        Return metadata for registered implementation.

    Args:
        stage (str): Stage namespace.
        name (str): Implementation identifier.

    Returns:
        dict[str, Any]: Registered metadata payload.

    Raises:
        ValueError: Raised when implementation key is not registered.
    """
    key = f"{stage}:{name}"
    if key not in IMPLEMENTATION_REGISTRY:
        raise ValueError(f"Implementation '{name}' for stage '{stage}' not found.")
    cls = IMPLEMENTATION_REGISTRY[key]
    return {
        "stage": stage,
        "name": name,
        "class": cls,
        "config_class": getattr(cls, "CONFIG_CLASS", None),
        "child_implementations": getattr(cls, "CHILD_IMPLEMENTATIONS", {}),
    }


def get_implementation_config_class(stage: str, name: str) -> str | None:
    """Generated: validation needed.

    Description:
        Return registered implementation config class.

    Args:
        stage (str): Stage namespace.
        name (str): Implementation identifier.

    Returns:
        str | None: Config class object or None.

    Raises:
        ValueError: Raised when implementation key is not registered.
    """
    key = f"{stage}:{name}"
    if key not in IMPLEMENTATION_REGISTRY:
        raise ValueError(f"Implementation '{name}' for stage '{stage}' not found.")
    cls = IMPLEMENTATION_REGISTRY[key]
    return getattr(cls, "CONFIG_CLASS", None)
