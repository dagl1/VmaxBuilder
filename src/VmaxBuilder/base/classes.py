from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from inspect import getmembers, isfunction
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from VmaxBuilder.base.configs import (
        InputSpec,
        OutputSpec,
        Scaffold,
    )


class BaseStageDiagnostics:
    """
    Only used for implementation-independent diagnostics used to verify stage output
    based on stage contracts.
    """

    def after_run(self, scaffold): ...


class ImplementationDiagnostics:
    """
    Used for implementation-specific diagnostics, which may include verifying
    stage output but also more detailed checks that may be specific
    to the implementation's approach.
    """

    def before_run(self, scaffold): ...
    def after_run(self, scaffold): ...
    def on_error(self, error): ...


class BaseImplementation(ABC):
    STAGE_NAME: str
    IMPL_NAME: str

    CONFIG_CLASS: type | None = None

    INPUTS: list["InputSpec"] = []
    OUTPUTS: list["OutputSpec"] = []

    CHILD_IMPLEMENTATIONS: list[type["BaseImplementation"]] = []

    DIAGNOSTICS: list[ImplementationDiagnostics] = []

    def __init__(self):
        self.child_implementations = [impl() for impl in self.CHILD_IMPLEMENTATIONS]

    def run(self, scaffold: "Scaffold") -> "Scaffold":
        new_scaffold_objects = self.generate_outputs(scaffold)
        scaffold.update_scaffold(new_scaffold_objects)

        return scaffold

    @abstractmethod
    def generate_outputs(self, scaffold: "Scaffold") -> dict[str, Any]:
        """
        Generate outputs based on the scaffold and return them as a dictionary.
        The keys of the dictionary should match the names of the outputs defined in OUTPUTS.
        This allows for all implementations and child implementations to a checkable contract
        for what they will produce before run-time. Each generate outputs can be checked
        in order, and a DAG can be created to follow the dependencies of each output.
        """
        pass

    def load_inputs(self, scaffold: "Scaffold") -> None:
        """
        Load the inputs specified in the INPUTS specification into the scaffold.
        This method can be overridden by subclasses to provide custom loading logic.
        """
        for input_spec in self.INPUTS:
            if scaffold.get_scaffold_location(input_spec.name):
                # If the input is already present in the scaffold, skip loading
                continue
            elif input_spec.loader and input_spec.file_key:
                # If a loader and file_key are specified, use the loader to load the input
                loaded_input = input_spec.loader(
                    input_spec.file_key,
                    **(input_spec.loader_args or {}),
                )
                scaffold.inputs[input_spec.name] = loaded_input
            elif not input_spec.optional:
                raise ValueError(
                    f"Cannot load input '{input_spec.name}': "
                    "No loader or file_key specified, and input not found in scaffold."
                )
            else:
                continue

    def validate_inputs(self, scaffold: "Scaffold") -> None:
        """
        Validate the inputs in the scaffold against the INPUTS specification.
        This method can be overridden by subclasses to provide custom validation logic.
        """
        for input_spec in self.INPUTS:
            if scaffold.get_scaffold_location(input_spec.name):
                raise ValueError(f"Missing required input: {input_spec.name}")
            # Additional validation logic can be added here based on input_spec properties
            #


@dataclass(frozen=True)
class FallbackProviderMetadata:
    provides: str
    requires: frozenset[str]


def fallback_provider(
    provides: str,
    requires: set[str] | None = None,
):
    requires_frozen = frozenset(requires or ())

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        setattr(  # noqa
            func,
            "_fallback_provider",
            FallbackProviderMetadata(provides=provides, requires=requires_frozen),
        )
        return func

    return decorator


def get_fallback_providers(cls):
    providers = {}

    for _, method in getmembers(cls, isfunction):
        metadata = getattr(method, "_fallback_provider", None)

        if metadata is not None:
            providers[metadata.provides] = metadata

    return providers
