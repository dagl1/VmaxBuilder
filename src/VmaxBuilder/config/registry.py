from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, TypeVar

T = TypeVar("T")

# ============================================================
# Registry Models
# ============================================================


@dataclass(frozen=True)
class ImplementationInfo:
    """Metadata for a registered implementation."""

    name: str
    implementation_class: type
    config_class: str | None = None

    description: str = ""
    version: str = "1.0"

    # optional extras
    tags: tuple[str, ...] = ()
    authors: tuple[str, ...] = ()


_REGISTRIES: dict[type, dict[str, ImplementationInfo]] = {}


# ============================================================
# Categories
# ============================================================


class ExpressionImplementation:
    """Marker type for expression methods."""


class TrimmingImplementation:
    """Marker type for trimming methods."""


class ProteomicsImplementation:
    """Marker type for proteomics methods."""


class PTRImplementation:
    """Marker type for PTR methods."""


class AllocationImplementation:
    """Marker type for allocation methods."""


# ============================================================
# Registration
# ============================================================


def register_implementation(
    category: type,
    *,
    name: str,
    config_class: str | None = None,
    description: str = "",
    version: str = "1.0",
    tags: tuple[str, ...] = (),
    authors: tuple[str, ...] = (),
) -> Callable[[type[T]], type[T]]:
    """
    Register an implementation for a category.
    """

    def decorator(cls: type[T]) -> type[T]:
        registry = _REGISTRIES.setdefault(category, {})

        if name in registry:
            raise ValueError(f"{category.__name__}.{name} already registered")

        registry[name] = ImplementationInfo(
            name=name,
            implementation_class=cls,
            config_class=config_class,
            description=description,
            version=version,
            tags=tags,
            authors=authors,
        )

        return cls

    return decorator


# ============================================================
# Lookup
# ============================================================


def get_implementation(category: type, name: str) -> type:
    try:
        return _REGISTRIES[category][name].implementation_class
    except KeyError:
        available = get_available_options(category)

        raise ValueError(
            f"Unknown {category.__name__}: '{name}'. Available: {', '.join(available)}"
        ) from None


def get_config_class(category: type, name: str) -> str | None:
    return _REGISTRIES[category][name].config_class


def get_info(category: type, name: str) -> ImplementationInfo:
    return _REGISTRIES[category][name]


def get_available_options(category: type) -> list[str]:
    return sorted(_REGISTRIES.get(category, {}))


# ============================================================
# Example Configs
# ============================================================


# ============================================================
# Example Implementations
# ============================================================


@register_implementation(
    ExpressionImplementation,
    name="minimal",
    config_class="MinimalExpressionConfig",
    description="Simple percentile-based filtering",
)
class MinimalExpression:
    pass


@register_implementation(
    ExpressionImplementation,
    name="tpm",
    config_class="TPMExpressionConfig",
    description="TPM normalization",
)
class TPMExpression:
    pass
