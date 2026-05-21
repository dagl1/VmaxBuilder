"""Generated: validation needed.

Description:
    Diagnostics runner implementation for orchestrator stage execution boundaries.

Args:
    None.

Returns:
    None.

Raises:
    None.

Requires:
    None.

Modifies:
    None.
"""

from __future__ import annotations

from collections.abc import Sequence

from VmaxBuilder.config.dataclasses import APIConfig
from VmaxBuilder.config.enums import DiagnosticSeverity, StageName
from VmaxBuilder.core.protocols import (
    DiagnosticRecord,
    DiagnosticsHookProtocol,
    DiagnosticsRunnerProtocol,
    Scaffold,
)

# ruff: noqa: I001


class DiagnosticsRunner(DiagnosticsRunnerProtocol):
    """Generated: validation needed.

    Description:
        Execute diagnostics hooks and append emitted records to scaffold diagnostics payload.

    Args:
        None.

    Returns:
        None.

    Raises:
        RuntimeError: When emitted diagnostics exceed configured halt severity threshold.

    Requires:
        None.

    Modifies:
        None.
    """

    _severity_rank: dict[DiagnosticSeverity, int] = {
        DiagnosticSeverity.DEBUG: 10,
        DiagnosticSeverity.INFO: 20,
        DiagnosticSeverity.WARNING: 30,
        DiagnosticSeverity.ERROR: 40,
        DiagnosticSeverity.CRITICAL: 50,
    }

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
            Run before-stage and after-stage diagnostics hooks and update
            scaffold diagnostics.

        Args:
            scaffold (Scaffold): Shared pipeline scaffold.
            config (APIConfig): Root API configuration.
            stage_name (StageName): Current stage name.
            hooks (Sequence[DiagnosticsHookProtocol]): Diagnostics hooks to run.
            method_key (str | None): Optional strategy key.

        Returns:
            Scaffold: Updated scaffold with diagnostics records.

        Raises:
            RuntimeError: When halt threshold is exceeded by emitted records.

        Requires:
            None.

        Modifies:
            scaffold["diagnostics"]: Appends diagnostics records under stage key.
        """

        stage_records: list[DiagnosticRecord] = []
        for hook in hooks:
            if hook.stage is not stage_name:
                continue
            stage_records.extend(
                hook.before_stage(
                    scaffold,
                    config=config,
                    method_key=method_key,
                )
            )
            stage_records.extend(
                hook.after_stage(
                    scaffold,
                    config=config,
                    method_key=method_key,
                )
            )

        diagnostics_payload = scaffold.setdefault("diagnostics", {})
        existing_records = diagnostics_payload.get(stage_name.value, [])
        diagnostics_payload[stage_name.value] = [*existing_records, *stage_records]

        if self._should_halt(stage_records, threshold=config.validation.halt_severity):
            raise RuntimeError(
                f"Diagnostics threshold reached for stage '{stage_name.value}'. "
                f"Configured threshold: '{config.validation.halt_severity.value}'."
            )
        return scaffold

    def _should_halt(
        self,
        records: Sequence[DiagnosticRecord],
        *,
        threshold: DiagnosticSeverity,
    ) -> bool:
        """Generated: validation needed.

        Description:
            Determine whether diagnostics records breach configured severity threshold.

        Args:
            records (Sequence[DiagnosticRecord]): Emitted diagnostics records.
            threshold (DiagnosticSeverity): Halt threshold.

        Returns:
            bool: True when threshold is met or exceeded.

        Raises:
            None.

        Requires:
            None.

        Modifies:
            None.
        """

        threshold_rank = self._severity_rank[threshold]
        for record in records:
            record_rank = self._severity_rank[record["severity"]]
            if record_rank >= threshold_rank:
                return True
        return False
