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
