"""Generated: validation needed.

Description:
    Base protocols and typed payloads for refactored VmaxBuilder API.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol, TypedDict, runtime_checkable

from VmaxBuilder.config.dataclasses import APIConfig
from VmaxBuilder.config.enums import DiagnosticSeverity, StageName


class Scaffold(TypedDict):
    """Generated: validation needed.

    Description:
        Shared pipeline scaffold passed between stages.

    Args:
        inputs (dict[str, Any]): Input artifact bag.
        artifacts (dict[str, Any]): Intermediate artifacts.
        outputs (dict[str, Any]): Final stage outputs.
        metadata (dict[str, Any]): Reproducibility metadata.
        diagnostics (dict[str, Any]): Diagnostics payload.
        extras (dict[str, Any]): Extension bag for custom modules.
    """

    inputs: dict[str, Any]
    artifacts: dict[str, Any]
    outputs: dict[str, Any]
    metadata: dict[str, Any]
    diagnostics: dict[str, Any]
    extras: dict[str, Any]


class DiagnosticRecordCore(TypedDict):
    """Generated: validation needed.

    Description:
        Core diagnostics fields for structured logging and stage inspection.

    Args:
        timestamp_utc (str): UTC timestamp for event.
        run_id (str): Stable run identifier.
        stage (str): Stage name.
        module (str): Module name.
        method (str): Strategy or implementation method.
        event (str): Event key.
        severity (str): Severity label.
        message (str): Human-readable diagnostic message.
        duration_ms (float): Event duration in milliseconds.
        cache_hit (bool): Whether cache was used.
        exception_type (str): Exception type when event captures failure.
    """

    timestamp_utc: str
    run_id: str
    stage: str
    module: str
    method: str
    event: str
    severity: DiagnosticSeverity
    message: str
    duration_ms: float
    cache_hit: bool
    exception_type: str


class DiagnosticRecord(DiagnosticRecordCore, total=False):
    """Generated: validation needed.

    Description:
        Extended diagnostics record with optional context fields.

    Args:
        sample_id (str): Optional sample identifier.
        task_id (str): Optional task identifier.
        reaction_id (str): Optional reaction identifier.
        gene_id (str): Optional gene identifier.
        input_hash (str): Optional input hash.
        config_hash (str): Optional config hash.
        worker_id (str): Optional worker identifier.
        artifact_path (str): Optional artifact path.
    """

    sample_id: str
    task_id: str
    reaction_id: str
    gene_id: str
    input_hash: str
    config_hash: str
    worker_id: str
    artifact_path: str


@runtime_checkable
class StageProtocol(Protocol):
    """Generated: validation needed.

    Description:
        Protocol for a top-level pipeline stage implementation.

    Requires:
        name (StageName): Stage name.
    """

    name: StageName

    def run(self, scaffold: Scaffold, config: APIConfig) -> Scaffold:
        """Generated: validation needed.

        Description:
            Execute stage against shared scaffold and API config.

        Args:
            scaffold (Scaffold): Shared pipeline scaffold.
            config (APIConfig): Root API configuration.

        Returns:
            Scaffold: Updated scaffold.
        """


@runtime_checkable
class StrategyProtocol(Protocol):
    """Generated: validation needed.

    Description:
        Protocol for interchangeable submodule strategy implementation.

    Requires:
        method_key (str): Strategy identifier.
    """

    method_key: str

    def run(self, scaffold: Scaffold, config: APIConfig) -> Scaffold:
        """Generated: validation needed.

        Description:
            Execute strategy against shared scaffold and API config.

        Args:
            scaffold (Scaffold): Shared pipeline scaffold.
            config (APIConfig): Root API configuration.

        Returns:
            Scaffold: Updated scaffold.
        """


@runtime_checkable
class DiagnosticsHookProtocol(Protocol):
    """Generated: validation needed.

    Description:
        Protocol for diagnostics hook attached to stage or strategy execution.

    Requires:
        stage (StageName): Stage this hook targets.
        name (str): Hook name.
    """

    stage: StageName
    name: str

    def before_stage(
        self,
        scaffold: Scaffold,
        *,
        config: APIConfig,
        method_key: str | None = None,
    ) -> Sequence[DiagnosticRecord]:
        """Generated: validation needed.

        Description:
            Inspect scaffold before stage execution.

        Args:
            scaffold (Scaffold): Shared pipeline scaffold.
            config (APIConfig): Root API configuration.
            method_key (str | None): Optional strategy key.

        Returns:
            Sequence[DiagnosticRecord]: Diagnostics emitted before stage execution.
        """

    def after_stage(
        self,
        scaffold: Scaffold,
        *,
        config: APIConfig,
        method_key: str | None = None,
    ) -> Sequence[DiagnosticRecord]:
        """Generated: validation needed.

        Description:
            Inspect scaffold after stage execution.

        Args:
            scaffold (Scaffold): Shared pipeline scaffold.
            config (APIConfig): Root API configuration.
            method_key (str | None): Optional strategy key.

        Returns:
            Sequence[DiagnosticRecord]: Diagnostics emitted after stage execution.
        """


@runtime_checkable
class DiagnosticsRunnerProtocol(Protocol):
    """Generated: validation needed.

    Description:
        Protocol for diagnostics runner coordinating hooks and halt policy.
    """

    def run_hooks(
        self,
        scaffold: Scaffold,
        *,
        config: APIConfig,
        stage_name: StageName,
        hooks: Sequence[DiagnosticsHookProtocol],
        method_key: str | None = None,
    ) -> Scaffold:
        """Generated: validation needed.

        Description:
            Run diagnostics hooks for one stage boundary.

        Args:
            scaffold (Scaffold): Shared pipeline scaffold.
            config (APIConfig): Root API configuration.
            stage_name (StageName): Current stage name.
            hooks (Sequence[DiagnosticsHookProtocol]): Diagnostics hooks to execute.
            method_key (str | None): Optional strategy key.

        Returns:
            Scaffold: Scaffold updated with diagnostics records.

        """


@runtime_checkable
class RegistryProtocol(Protocol):
    """Generated: validation needed.

    Description:
        Protocol for explicit registry used by stage, strategy, or hook lookup.
    """

    def register(self, key: str, value: Any) -> None:
        """Generated: validation needed.

        Description:
            Register implementation under explicit key.

        Args:
            key (str): Registry key.
            value (Any): Implementation object.

        """

    def resolve(self, key: str) -> Any:
        """Generated: validation needed.

        Description:
            Resolve one registered implementation.

        Args:
            key (str): Registry key.

        Returns:
            Any: Registered implementation.

        Raises:
            KeyError: When key is not registered.
        """

    def available(self) -> tuple[str, ...]:
        """Generated: validation needed.

        Description:
            Return available registry keys.

        Returns:
            tuple[str, ...]: Registered keys.
        """
