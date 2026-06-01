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
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd

from VmaxBuilder.api.allocation import AllocationStageOrchestrator
from VmaxBuilder.api.model import ModelStageOrchestrator
from VmaxBuilder.api.protein import ProteinStageOrchestrator
from VmaxBuilder.api.vmax import VmaxStageOrchestrator
from VmaxBuilder.config import ConfigurationError
from VmaxBuilder.config.dataclasses import APIConfig
from VmaxBuilder.config.enums import StageName
from VmaxBuilder.config.validation import validate_loading_policy
from VmaxBuilder.core.protocols import (
    DiagnosticsHookProtocol,
    DiagnosticsRunnerProtocol,
    Scaffold,
    StageProtocol,
)
from VmaxBuilder.diagnostics.runner import DiagnosticsRunner
from VmaxBuilder.protein.stage_implementation import DefaultProteinStageCoordinator
from VmaxBuilder.utils.file_handling import save_with_tries

# ruff:

_ARTIFACTS_DIRECTORY_NAME = "artifacts"
_DIAGNOSTICS_DIRECTORY_NAME = "diagnostics"
_METADATA_DIRECTORY_NAME = "metadata"
_OUTPUTS_DIRECTORY_NAME = "outputs"


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
        self._persist_runtime_state(scaffold=working_scaffold, stage_name=StageName.MODEL)
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
        self._persist_runtime_state(scaffold=working_scaffold, stage_name=StageName.PROTEIN)
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
        self._persist_runtime_state(
            scaffold=working_scaffold,
            stage_name=StageName.ALLOCATION,
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
        self._persist_runtime_state(scaffold=working_scaffold, stage_name=StageName.VMAX)
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

        validate_loading_policy(self.config.loading, validation_policy=self.config.validation)
        self._prime_output_directories(scaffold=scaffold)
        if stage_name is StageName.MODEL:
            self._validate_model_inputs(scaffold=scaffold)
        elif stage_name is StageName.PROTEIN:
            self._validate_protein_inputs(scaffold=scaffold)

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

    def _validate_protein_inputs(self, *, scaffold: Scaffold) -> None:
        """Generated: validation needed.

        Description:
            Validate protein-stage inputs are available from in-memory objects or path config.
            Required inputs depend on protein.source_mode (expression+ptr or proteomics).

        Args:
            scaffold (Scaffold): Shared pipeline scaffold.

        Raises:
            ConfigurationError: When required protein inputs are missing.
        """

        mode_requirements = DefaultProteinStageCoordinator.get_mode_requirements(
            self.config.protein.source_mode
        )
        required_inputs: tuple[str, ...] = mode_requirements["required_inputs"]

        in_memory_inputs = self.config.loading.get_effective_in_memory_inputs()
        explicit_paths = self.config.loading.get_effective_exact_paths()

        missing_inputs: list[str] = []
        for input_key in required_inputs:
            has_in_memory = input_key in in_memory_inputs
            input_path = explicit_paths.get(input_key)
            has_path = input_path is not None and Path(input_path).exists()
            if not has_in_memory and not has_path:
                missing_inputs.append(input_key)

        if missing_inputs:
            raise ConfigurationError(
                "Missing required protein inputs for mode "
                f"'{self.config.protein.source_mode.value}': {missing_inputs}. "
                "Set required *_path values to existing files or provide in_memory_inputs."
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

        resolved_output_directory = self.config.loading.get_resolved_output_directory()
        output_directories = self.config.loading.get_output_directories()
        current_signature = self._build_output_signature(output_directories)
        if not current_signature or current_signature == self._last_primed_output_paths:
            return

        for output_directory in output_directories:
            output_directory.mkdir(parents=True, exist_ok=True)

        orchestrator_metadata = scaffold.setdefault("metadata", {}).setdefault(
            "orchestrator", {}
        )
        orchestrator_metadata["resolved_output_directory"] = str(resolved_output_directory)
        orchestrator_metadata["artifact_directory"] = str(
            resolved_output_directory / _ARTIFACTS_DIRECTORY_NAME
        )
        orchestrator_metadata["diagnostics_directory"] = str(
            resolved_output_directory / _DIAGNOSTICS_DIRECTORY_NAME
        )
        orchestrator_metadata["metadata_directory"] = str(
            resolved_output_directory / _METADATA_DIRECTORY_NAME
        )
        orchestrator_metadata["outputs_directory"] = str(
            resolved_output_directory / _OUTPUTS_DIRECTORY_NAME
        )
        orchestrator_metadata["primed_output_directories"] = [
            str(directory) for directory in output_directories
        ]
        self._last_primed_output_paths = current_signature

    def _persist_runtime_state(self, *, scaffold: Scaffold, stage_name: StageName) -> None:
        """Generated: validation needed.

        Description:
            Persist scaffold artifacts, diagnostics, outputs, and metadata into
            resolved run output directories.

        Args:
            scaffold (Scaffold): Shared pipeline scaffold.
            stage_name (StageName): Stage most recently executed.

        Modifies:
            Filesystem output directory contents and scaffold metadata manifest paths.
        """

        resolved_output_directory = self.config.loading.get_resolved_output_directory()
        artifacts_directory = resolved_output_directory / _ARTIFACTS_DIRECTORY_NAME
        diagnostics_directory = resolved_output_directory / _DIAGNOSTICS_DIRECTORY_NAME
        metadata_directory = resolved_output_directory / _METADATA_DIRECTORY_NAME
        outputs_directory = resolved_output_directory / _OUTPUTS_DIRECTORY_NAME

        artifact_manifest = self._persist_named_payloads(
            payload=scaffold.get("artifacts", {}),
            save_directory=artifacts_directory,
        )
        output_manifest = self._persist_named_payloads(
            payload=scaffold.get("outputs", {}),
            save_directory=outputs_directory,
        )
        diagnostics_payload = self._make_json_safe(scaffold.get("diagnostics", {}))
        metadata_payload = self._make_json_safe(scaffold.get("metadata", {}))
        self._save_json_payload(
            payload=diagnostics_payload,
            filename="scaffold_diagnostics",
            save_directory=diagnostics_directory,
        )
        self._save_json_payload(
            payload=metadata_payload,
            filename="scaffold_metadata",
            save_directory=metadata_directory,
        )

        stage_diagnostics = diagnostics_payload.get(stage_name.value)
        if stage_diagnostics is not None:
            self._save_json_payload(
                payload=stage_diagnostics,
                filename=f"{stage_name.value}_diagnostics",
                save_directory=diagnostics_directory,
            )

        orchestrator_metadata = scaffold.setdefault("metadata", {}).setdefault(
            "orchestrator", {}
        )
        orchestrator_metadata["last_persisted_stage"] = stage_name.value
        orchestrator_metadata["artifact_manifest_path"] = str(
            artifacts_directory / "artifact_manifest.json"
        )
        orchestrator_metadata["output_manifest_path"] = str(
            outputs_directory / "output_manifest.json"
        )
        self._save_json_payload(
            payload=artifact_manifest,
            filename="artifact_manifest",
            save_directory=artifacts_directory,
        )
        self._save_json_payload(
            payload=output_manifest,
            filename="output_manifest",
            save_directory=outputs_directory,
        )
        self._save_json_payload(
            payload=self._make_json_safe(scaffold.get("metadata", {})),
            filename="scaffold_metadata",
            save_directory=metadata_directory,
        )

    def _persist_named_payloads(
        self,
        *,
        payload: dict[str, Any],
        save_directory: Path,
    ) -> dict[str, dict[str, str]]:
        """Generated: validation needed.

        Description:
            Persist serialisable scaffold payload entries and return save manifest.

        Args:
            payload (dict[str, Any]): Named scaffold section payload.
            save_directory (Path): Directory receiving persisted files.

        Returns:
            dict[str, dict[str, str]]: Per-entry save status manifest.
        """

        manifest: dict[str, dict[str, str]] = {}
        for payload_name, payload_value in payload.items():
            manifest[payload_name] = self._persist_named_value(
                payload_name=payload_name,
                payload_value=payload_value,
                save_directory=save_directory,
            )
        return manifest

    def _persist_named_value(
        self,
        *,
        payload_name: str,
        payload_value: Any,
        save_directory: Path,
    ) -> dict[str, str]:
        """Generated: validation needed.

        Description:
            Persist one named scaffold value when supported by runtime serializers.

        Args:
            payload_name (str): Stable scaffold payload key.
            payload_value (Any): Payload value to persist.
            save_directory (Path): Target directory.

        Returns:
            dict[str, str]: Save status, type, and optional path or skip reason.
        """

        if isinstance(payload_value, pd.DataFrame):
            saved_path = self._save_tabular_payload(
                payload=payload_value,
                filename=payload_name,
                save_directory=save_directory,
                include_index=True,
            )
            return {
                "status": "saved",
                "type": type(payload_value).__name__,
                "path": str(saved_path),
            }

        if isinstance(payload_value, pd.Series):
            saved_path = self._save_tabular_payload(
                payload=payload_value,
                filename=payload_name,
                save_directory=save_directory,
                include_index=True,
            )
            return {
                "status": "saved",
                "type": type(payload_value).__name__,
                "path": str(saved_path),
            }

        if isinstance(payload_value, (dict, list, tuple, set)):
            saved_path = self._save_json_payload(
                payload=self._make_json_safe(payload_value),
                filename=payload_name,
                save_directory=save_directory,
            )
            return {
                "status": "saved",
                "type": type(payload_value).__name__,
                "path": str(saved_path),
            }

        if isinstance(payload_value, (str, int, float, bool, Path)) or payload_value is None:
            saved_path = self._save_text_payload(
                payload=str(payload_value),
                filename=payload_name,
                save_directory=save_directory,
            )
            return {
                "status": "saved",
                "type": type(payload_value).__name__,
                "path": str(saved_path),
            }

        return {
            "status": "skipped",
            "type": type(payload_value).__name__,
            "reason": "unsupported_runtime_type",
        }

    @staticmethod
    def _save_tabular_payload(
        *,
        payload: pd.DataFrame | pd.Series,
        filename: str,
        save_directory: Path,
        include_index: bool,
    ) -> Path:
        """Generated: validation needed.

        Description:
            Save tabular runtime payload as CSV for user inspection.

        Args:
            payload (pd.DataFrame | pd.Series): Tabular payload.
            filename (str): Output filename stem.
            save_directory (Path): Target directory.
            include_index (bool): Whether to include index column.

        Returns:
            Path: Saved CSV path.
        """

        save_with_tries(
            data=payload,
            filename=filename,
            extension="csv",
            save_dir=save_directory,
            overwrite=True,
            with_index=include_index,
        )
        return save_directory / f"{filename}.csv"

    @staticmethod
    def _save_json_payload(
        *,
        payload: dict[str, Any] | list[Any],
        filename: str,
        save_directory: Path,
    ) -> Path:
        """Generated: validation needed.

        Description:
            Save JSON-serialisable runtime payload.

        Args:
            payload (dict[str, Any] | list[Any]): JSON-safe payload.
            filename (str): Output filename stem.
            save_directory (Path): Target directory.

        Returns:
            Path: Saved JSON path.
        """

        save_with_tries(
            data=payload,
            filename=filename,
            extension="json",
            save_dir=save_directory,
            overwrite=True,
        )
        return save_directory / f"{filename}.json"

    @staticmethod
    def _save_text_payload(
        *,
        payload: str,
        filename: str,
        save_directory: Path,
    ) -> Path:
        """Generated: validation needed.

        Description:
            Save scalar runtime payload as plain text.

        Args:
            payload (str): Text payload.
            filename (str): Output filename stem.
            save_directory (Path): Target directory.

        Returns:
            Path: Saved text path.
        """

        save_with_tries(
            data=payload,
            filename=filename,
            extension="txt",
            save_dir=save_directory,
            overwrite=True,
        )
        return save_directory / f"{filename}.txt"

    @classmethod
    def _make_json_safe(cls, value: Any) -> Any:
        """Generated: validation needed.

        Description:
            Convert nested runtime payloads into JSON-safe builtin values.

        Args:
            value (Any): Runtime payload value.

        Returns:
            Any: JSON-safe builtin representation.
        """

        if isinstance(value, dict):
            return {
                str(key): cls._make_json_safe(nested_value)
                for key, nested_value in value.items()
            }
        if isinstance(value, (list, tuple, set)):
            return [cls._make_json_safe(item) for item in value]
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, pd.Index):
            return [cls._make_json_safe(item) for item in value.tolist()]
        if isinstance(value, pd.Series):
            return cls._make_json_safe(value.to_dict())
        if hasattr(value, "item") and callable(value.item):
            try:
                return value.item()
            except (TypeError, ValueError):
                pass
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        return str(value)

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
