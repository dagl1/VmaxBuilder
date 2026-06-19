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
# protocol/architecture
# ============================================================
"""
orchestrator ->
    stages:
        populated by implementation,
            if CHILD implmeplentations, then no config
            if no CHILD_IMPLEMENTATIONS then implemnetation has config

## creating a final implemenation requires only a config class and run method
## compositing multiple implementations into a single stage is done by creating a new
    implementation that has CHILD_IMPLEMENTATIONS and no config class
## optionally an implementation can have a diagnostics hook attached

# implementation file structure should look like:
    Required:
        stage_name/implementation_name/implementation.py (imports config, diagnostics, enums, dataclasses)

    Required if no child implementations:
        stage_name/implementation_name/config.py

    Optionally:
        stage_name/implementation_name/diangostics.py
        stage_name/implementation_name/enums.py
        stage_name/implementation_name/dataclasses.py

# each implementation has a stage_name attached to it, such that we can check
# whether the implemneation follows the protocol, or following the child implementations in order
# follows the protocols (so last protocol returns the final scaffold, according to SpecificStageProtocol)
# required inputs are defined in the implementation
# to validate that scaffold is properly updated on return, the actual protocol check is
to_load_inputs will designate which inputs should be preloaded versus created by the implementation
#


## each stage has a protocol on what it should return

to validate inputs, we walk down the implementations and ensure that the required inputs
are present, for child implementations we ensure that the get_scaffold_objects returns the
required inputs for the next implementation, and so on. We then also cast it such that
type checking can be done on the scaffold,
and we can ensure that the final scaffold is properly typed.
specific time, debug, and save artifacts are present on all implementations.


"""


class BaseStageProtocol:
    """Protocol for stage orchestrators."""

    name: str | None = None


class ModelStageProtocol(BaseStageProtocol):
    """Protocol for model stage orchestrators."""

    name: str = "model"

    def run(self, scaffold: dict, config: Any) -> dict:
        """Run the model stage.

        Args:
            scaffold (dict): Shared pipeline scaffold.
            config (Any): Root API configuration.

        Returns:
            dict: Updated scaffold.
        """
        raise NotImplementedError

    def get_implementation(self, name: str) -> type:
        """Get the implementation class for a given name.

        Args:
            name (str): Name of the implementation.

        """


@dataclass
class InputInfo:
    """Information about a required input for a stage implementation."""

    name: str
    description: str = ""
    type: type | None = None
    optional: bool = False
    suffix: str | None = None


class ImplementationProtocol:
    """Protocol for stage implementations."""

    STAGE_NAME: str | None = None
    required_inputs: list[str] = []  # from scaffold
    to_load_inputs: list[
        InputInfo
    ] = []  # tells stage orchestrator which files should be preloaded from disk
    CHILD_IMPLEMENTATIONS: dict[str, type] = {}
    CONFIG_CLASS: str | None = None

    def run(self, scaffold: dict, config: Any) -> dict:
        """Run the stage implementation.

        Args:
            scaffold (dict): Shared pipeline scaffold.
            config (Any): Root API configuration.

        Returns:
            dict: Updated scaffold.
        """
        if not CHILD_IMPLEMENTATIONS:
            self.validate_scaffold(scaffold)
            self.validate_config(config)
            self.validate_required_inputs(
                scaffold
            )  # first validates inputs at this level, then walks down the child implementations to validate their required inputs
            scaffold_objects = self.get_scaffold_objects(scaffold)
            scaffold.update(scaffold_objects)
            return scaffold
        for child_name, child_impl in self.CHILD_IMPLEMENTATIONS.items():
            child_instance = child_impl()
            scaffold = child_instance.run(scaffold, config)

    def get_scaffold_objects(self, scaffold: dict) -> dict:
        """Get the required scaffold objects for this implementation.

        Args:
            scaffold (dict): Shared pipeline scaffold.

        Returns:
            dict: Required scaffold objects.
        """


class BaseImplementation:
    STAGE_NAME: str | None = None
    CONFIG_CLASS: str | None = None
    CHILD_IMPLEMENTATIONS: dict[str, type] = {}
