"""Generated: validation needed.

Description:
    Main orchestrator for refactored VmaxBuilder stage execution.

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
from pathlib import Path

from VmaxBuilder.api.allocation import AllocationStageOrchestrator
from VmaxBuilder.api.model import ModelStageOrchestrator
from VmaxBuilder.api.protein import ProteinStageOrchestrator
from VmaxBuilder.api.vmax import VmaxStageOrchestrator
from VmaxBuilder.config import ConfigurationError
from VmaxBuilder.config.dataclasses import APIConfig
from VmaxBuilder.config.enums import StageName
from VmaxBuilder.core.protocols import (
    DiagnosticsHookProtocol,
    DiagnosticsRunnerProtocol,
    Scaffold,
    StageProtocol,
)
from VmaxBuilder.diagnostics.runner import DiagnosticsRunner

# ruff:


def build_default_api_config() -> APIConfig:
    """Generated: validation needed.

    Description:
        Build default API configuration object for caller-side field assignment.

    Returns:
        APIConfig: Fresh APIConfig with default values.

    Example:
        >>> config = build_default_api_config()
        >>> config.model.make_copy = False
        >>> config.loading.model_path = Path("C:/data/model.json")
    """

    return APIConfig()


class VmaxOrchestrator:
    """Generated: validation needed.

    Description:
        Orchestrate configured pipeline stages over shared scaffold.

    Args:
        config (APIConfig): Root API config object.
        model_stage (StageProtocol | None): Optional model stage implementation override.
        protein_stage (StageProtocol | None): Optional protein stage implementation override.
        allocation_stage (StageProtocol | None):
            Optional allocation stage implementation override.
        vmax_stage (StageProtocol | None): Optional vmax stage implementation override.
        diagnostics_runner (DiagnosticsRunnerProtocol | None):
            Optional diagnostics runner override.
        diagnostics_hooks (Sequence[DiagnosticsHookProtocol] | None):
            Optional diagnostics hooks.

    Returns:
        None.

    Raises:
        None.

    Requires:
        None.

    Modifies:
        None.
    """

    def __init__(
        self,
        config: APIConfig | None = None,
        *,
        model_stage: StageProtocol | None = None,
        protein_stage: StageProtocol | None = None,
        allocation_stage: StageProtocol | None = None,
        vmax_stage: StageProtocol | None = None,
        diagnostics_runner: DiagnosticsRunnerProtocol | None = None,
        diagnostics_hooks: Sequence[DiagnosticsHookProtocol] | None = None,
    ) -> None:
        """Generated: validation needed.

        Description:
            Initialize stage implementations and diagnostics wiring.

        Args:
            config (APIConfig | None): Root API configuration.
            model_stage (StageProtocol | None): Model stage override.
            protein_stage (StageProtocol | None): Protein stage override.
            allocation_stage (StageProtocol | None): Allocation stage override.
            vmax_stage (StageProtocol | None): Vmax stage override.
            diagnostics_runner (DiagnosticsRunnerProtocol | None):
                Diagnostics runner override.
            diagnostics_hooks (Sequence[DiagnosticsHookProtocol] | None): Diagnostics hooks.

        Returns:
            None.

        Raises:
            None.

        Requires:
            None.

        Modifies:
            self.config and stage implementation references.
        """

        self.config = config or APIConfig()
        self.model_stage = model_stage or ModelStageOrchestrator()
        self.protein_stage = protein_stage or ProteinStageOrchestrator()
        self.allocation_stage = allocation_stage or AllocationStageOrchestrator()
        self.vmax_stage = vmax_stage or VmaxStageOrchestrator()
        self.diagnostics_runner = diagnostics_runner or DiagnosticsRunner()
        self.diagnostics_hooks = tuple(diagnostics_hooks or ())
        self._last_primed_output_paths: tuple[str, ...] | None = None

    def run_model(self, scaffold: Scaffold | None = None) -> Scaffold:
        """Generated: validation needed.

        Description:
            Execute model stage and return updated scaffold.

        Args:
            scaffold (Scaffold | None): Optional existing scaffold.

        Returns:
            Scaffold: Updated scaffold after model stage execution.

        Modifies:
            scaffold payload.
        """

        working_scaffold = self._initialise_scaffold(scaffold)
        self._ensure_runtime_ready(stage_name=StageName.MODEL, scaffold=working_scaffold)
        working_scaffold = self.model_stage.run(working_scaffold, self.config)
        working_scaffold = self.diagnostics_runner.run_hooks(
            working_scaffold,
            config=self.config,
            stage_name=StageName.MODEL,
            hooks=self.diagnostics_hooks,
            method_key=self.config.model.method,
        )
        return working_scaffold

    def run_protein(self, scaffold: Scaffold | None = None) -> Scaffold:
        """Generated: validation needed.

        Description:
            Execute protein stage and return updated scaffold.

        Args:
            scaffold (Scaffold | None): Optional existing scaffold.

        Returns:
            Scaffold: Updated scaffold after protein stage execution.

        Modifies:
            scaffold payload.
        """

        working_scaffold = self._initialise_scaffold(scaffold)
        self._ensure_runtime_ready(stage_name=StageName.PROTEIN, scaffold=working_scaffold)
        working_scaffold = self.protein_stage.run(working_scaffold, self.config)
        working_scaffold = self.diagnostics_runner.run_hooks(
            working_scaffold,
            config=self.config,
            stage_name=StageName.PROTEIN,
            hooks=self.diagnostics_hooks,
            method_key=self.config.protein.method,
        )
        return working_scaffold

    def run_allocation(self, scaffold: Scaffold | None = None) -> Scaffold:
        """Generated: validation needed.

        Description:
            Execute allocation stage and return updated scaffold.

        Args:
            scaffold (Scaffold | None): Optional existing scaffold.

        Returns:
            Scaffold: Updated scaffold after allocation stage execution.

        Modifies:
            scaffold payload.
        """

        working_scaffold = self._initialise_scaffold(scaffold)
        self._ensure_runtime_ready(stage_name=StageName.ALLOCATION, scaffold=working_scaffold)
        working_scaffold = self.allocation_stage.run(working_scaffold, self.config)
        working_scaffold = self.diagnostics_runner.run_hooks(
            working_scaffold,
            config=self.config,
            stage_name=StageName.ALLOCATION,
            hooks=self.diagnostics_hooks,
            method_key=self.config.allocation.method,
        )
        return working_scaffold

    def run_vmax(self, scaffold: Scaffold | None = None) -> Scaffold:
        """Generated: validation needed.

        Description:
            Execute vmax stage and return updated scaffold.

        Args:
            scaffold (Scaffold | None): Optional existing scaffold.

        Returns:
            Scaffold: Updated scaffold after vmax stage execution.

        Raises:
            None.

        Requires:
            None.

        Modifies:
            scaffold payload.
        """

        working_scaffold = self._initialise_scaffold(scaffold)
        self._ensure_runtime_ready(stage_name=StageName.VMAX, scaffold=working_scaffold)
        working_scaffold = self.vmax_stage.run(working_scaffold, self.config)
        working_scaffold = self.diagnostics_runner.run_hooks(
            working_scaffold,
            config=self.config,
            stage_name=StageName.VMAX,
            hooks=self.diagnostics_hooks,
            method_key=self.config.vmax.method,
        )
        return working_scaffold

    def run(self, stages: Sequence[StageName]) -> Scaffold:
        """Generated: validation needed.

        Description:
            Execute selected stages in provided order.

        Args:
            stages (Sequence[StageName]): Ordered list of stage names to execute.

        Returns:
            Scaffold: Updated scaffold after requested stage execution.

        Raises:
            ValueError: When unsupported stage name is provided.

        Modifies:
            scaffold payload across stage runs.
        """

        scaffold = self._initialise_scaffold()
        for stage_name in stages:
            if stage_name is StageName.MODEL:
                scaffold = self.run_model(scaffold)
            elif stage_name is StageName.PROTEIN:
                scaffold = self.run_protein(scaffold)
            elif stage_name is StageName.ALLOCATION:
                scaffold = self.run_allocation(scaffold)
            elif stage_name is StageName.VMAX:
                scaffold = self.run_vmax(scaffold)
            else:
                raise ValueError(f"Unsupported stage: {stage_name!s}")
        return scaffold

    def run_all(self) -> Scaffold:
        """Generated: validation needed.

        Description:
            Execute all top-level stages in default pipeline order.

        Returns:
            Scaffold: Updated scaffold after full pipeline traversal.

        Modifies:
            scaffold payload.
        """

        return self.run(
            stages=(
                StageName.MODEL,
                StageName.PROTEIN,
                StageName.ALLOCATION,
                StageName.VMAX,
            )
        )

    @staticmethod
    def _initialise_scaffold(scaffold: Scaffold | None = None) -> Scaffold:
        """Generated: validation needed.

        Description:
            Ensure scaffold contains required top-level payload sections.

        Args:
            scaffold (Scaffold | None): Optional existing scaffold payload.

        Returns:
            Scaffold: Normalized scaffold object.

        Modifies:
            scaffold dictionary keys when missing.
        """

        if scaffold is None:
            return {
                "inputs": {},
                "artifacts": {},
                "outputs": {},
                "metadata": {},
                "diagnostics": {},
                "extras": {},
            }
        scaffold.setdefault("inputs", {})
        scaffold.setdefault("artifacts", {})
        scaffold.setdefault("outputs", {})
        scaffold.setdefault("metadata", {})
        scaffold.setdefault("diagnostics", {})
        scaffold.setdefault("extras", {})
        return scaffold

    def _ensure_runtime_ready(self, *, stage_name: StageName, scaffold: Scaffold) -> None:
        """Generated: validation needed.

        Description:
            Prime output directories and validate stage runtime prerequisites.

        Args:
            stage_name (StageName): Stage that is about to run.
            scaffold (Scaffold): Shared pipeline scaffold.

        Raises:
            ConfigurationError: When required stage inputs are missing.
        """

        self._prime_output_directories(scaffold=scaffold)
        if stage_name is StageName.MODEL:
            self._validate_model_inputs(scaffold=scaffold)

    def _validate_model_inputs(self, *, scaffold: Scaffold) -> None:
        """Generated: validation needed.

        Description:
            Validate model-stage input is available from in-memory object or path config.

        Args:
            scaffold (Scaffold): Shared pipeline scaffold.

        Raises:
            ConfigurationError: When no model object/path/discovery roots are configured.
        """

        scaffold_inputs = scaffold.setdefault("inputs", {})
        if scaffold_inputs.get("model") is not None:
            return

        in_memory_inputs = self.config.loading.get_effective_in_memory_inputs()
        if in_memory_inputs.get("model") is not None:
            return

        explicit_paths = self.config.loading.get_effective_exact_paths()
        if explicit_paths.get("model") is not None:
            return

        if self.config.loading.iter_search_roots("model"):
            return

        raise ConfigurationError(
            "Model input missing: provide scaffold.inputs['model'], "
            "config.loading.model_object, config.loading.model_path, "
            "config.loading.exact_paths['model'], or config.loading.search_roots."
        )

    def _prime_output_directories(self, *, scaffold: Scaffold) -> None:
        """Generated: validation needed.

        Description:
            Ensure configured output directories exist, and re-prime when paths change.

        Args:
            scaffold (Scaffold): Shared pipeline scaffold.

        Modifies:
            Filesystem output directories and scaffold metadata.
        """

        output_directories = self.config.loading.get_output_directories()
        current_signature = self._build_output_signature(output_directories)
        if not current_signature or current_signature == self._last_primed_output_paths:
            return

        for output_directory in output_directories:
            output_directory.mkdir(parents=True, exist_ok=True)

        orchestrator_metadata = scaffold.setdefault("metadata", {}).setdefault(
            "orchestrator", {}
        )
        orchestrator_metadata["primed_output_directories"] = [
            str(directory) for directory in output_directories
        ]
        self._last_primed_output_paths = current_signature

    @staticmethod
    def _build_output_signature(output_directories: tuple[Path, ...]) -> tuple[str, ...]:
        """Generated: validation needed.

        Description:
            Build stable output-directory signature used for output re-prime checks.

        Args:
            output_directories (tuple[Path, ...]): Candidate output directories.

        Returns:
            tuple[str, ...]: Sorted normalized output path strings.
        """

        return tuple(sorted(str(directory.resolve()) for directory in output_directories))
