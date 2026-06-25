"""Generated: validation needed.

Description:
    Base protocols and typed payloads for refactored VmaxBuilder API.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    Protocol,
    TypedDict,
    overload,
    runtime_checkable,
)

from VmaxBuilder.base.enums import DiagnosticSeverity

if TYPE_CHECKING:
    from VmaxBuilder.base.configs import Scaffold

from cobra import Model


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
