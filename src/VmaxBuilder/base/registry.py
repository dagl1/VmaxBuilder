from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, TypeVar

from VmaxBuilder.base.classes import BaseImplementation

T = TypeVar("T")

# ============================================================
# Registry Models
# ============================================================
IMPLEMENTATION_REGISTRY: dict[str, type["BaseImplementation"]] = {}

STAGE_IMPLEMENTATIONS: defaultdict[str, list[str]] = defaultdict(list)


def register_implementation(stage: str, name: str):
    def decorator(cls):
        key = f"{stage}:{name}"
        IMPLEMENTATION_REGISTRY[key] = cls

        STAGE_IMPLEMENTATIONS.setdefault(stage, []).append(name)

        cls.STAGE_NAME = stage
        cls.IMPL_NAME = name

        return cls

    return decorator


def get_available_stages() -> list[str]:
    stages = set()
    for key in IMPLEMENTATION_REGISTRY.keys():
        stage, _ = key.split(":")
        stages.add(stage)
    return sorted(stages)


def get_available_implementations(stage: str) -> list[str]:
    implementations = []
    for key in IMPLEMENTATION_REGISTRY.keys():
        s, name = key.split(":")
        if s == stage:
            implementations.append(name)
    return sorted(implementations)


def get_implementation_info(stage: str, name: str) -> dict[str, Any]:
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
    key = f"{stage}:{name}"
    if key not in IMPLEMENTATION_REGISTRY:
        raise ValueError(f"Implementation '{name}' for stage '{stage}' not found.")
    cls = IMPLEMENTATION_REGISTRY[key]
    return getattr(cls, "CONFIG_CLASS", None)
