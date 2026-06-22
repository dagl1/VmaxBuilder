from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from VmaxBuilder.base.configs import InputSpec, OutputSpec, Scaffold


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

    CHILD_IMPLEMENTATIONS: dict[str, str] = {}

    DIAGNOSTICS: list[ImplementationDiagnostics] = []

    def run(self, scaffold: "Scaffold") -> "Scaffold":
            scaffold_objects =



    @abstractmethod
