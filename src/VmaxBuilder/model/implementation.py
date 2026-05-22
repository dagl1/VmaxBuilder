from __future__ import annotations

from pathlib import Path
from typing import Any

from cobra import Model

from VmaxBuilder.config.dataclasses import APIConfig
from VmaxBuilder.config.validation import (
    ConfigurationError,
    validate_loading_policy,
    validate_model_config,
)
from VmaxBuilder.core.protocols import Scaffold
from VmaxBuilder.model.preprocessing import preprocess_model
from VmaxBuilder.utils.file_handling import load_existing_file_based_on_extension

_ALLOWED_MODEL_SUFFIXES = {".json", ".xml", ".mat"}


class DefaultModelStageImplementation:
    """Generated: validation needed.

    Description:
        Validate model/loading configuration and resolve model input reference.

    Raises:
        ConfigurationError: When model resolution input is missing.

    Modifies:
        scaffold payload for model stage artifacts and metadata.
    """

    def run(self, scaffold: Scaffold, config: APIConfig) -> Scaffold:
        """Generated: validation needed.

        Description:
            Execute model-stage implementation and attach artifacts/metadata to scaffold.

        Args:
            scaffold (Scaffold): Shared pipeline scaffold.
            config (APIConfig): Root API configuration.

        Returns:
            Scaffold: Updated scaffold with model-stage payload.

        Raises:
            ConfigurationError: When no model path or search roots are configured.

        Modifies:
            scaffold["artifacts"] and scaffold["metadata"].
        """

        validate_model_config(config.model, validation_policy=config.validation)
        validate_loading_policy(config.loading, validation_policy=config.validation)

        model_object, model_reference = self._resolve_model_input(config, scaffold)
        preprocessing_result = preprocess_model(model_object, config.model)
        artifacts_payload = scaffold.setdefault("artifacts", {})
        metadata_payload = scaffold.setdefault("metadata", {})

        artifacts_payload["model_reference"] = model_reference
        artifacts_payload["model"] = preprocessing_result["irreversible_model"]
        artifacts_payload["rev2irrev"] = preprocessing_result["rev2irrev"]
        metadata_payload["model_stage"] = {
            "reaction_notation": config.model.reaction_notation.value,
            "make_copy": config.model.make_copy,
        }
        return scaffold

    def _resolve_model_input(
        self, config: APIConfig, scaffold: Scaffold
    ) -> tuple[Model, dict[str, Any]]:
        """Generated: validation needed.

        Description:
            Resolve model reference from explicit path or configured discovery roots.

        Args:
            config (APIConfig): Root API configuration.
            scaffold (Scaffold): Shared pipeline scaffold.

        Returns:
            tuple[cobra.Model, dict[str, Any]]: Loaded model object and
            model reference metadata.

        Raises:
            ConfigurationError: When explicit path and discovery roots are both absent.
        """

        input_payload = scaffold.setdefault("inputs", {})
        in_memory_inputs = config.loading.get_effective_in_memory_inputs()
        model_object = input_payload.get("model", in_memory_inputs.get("model"))
        if model_object is not None:
            if not isinstance(model_object, Model):
                raise ConfigurationError(
                    "Model input must be cobra.Model when provided in-memory. "
                    f"Received {type(model_object).__name__}."
                )
            input_payload["model"] = model_object
            return model_object, {
                "source": "in_memory",
                "object_type": type(model_object).__name__,
            }

        explicit_paths = config.loading.get_effective_exact_paths()
        model_path = explicit_paths.get("model")
        if model_path is not None:
            resolved_model_path = self._resolve_model_file_path(model_path)
            loaded_model = self._load_model_from_path(resolved_model_path)
            input_payload["model"] = loaded_model
            return loaded_model, {
                "source": "explicit_path",
                "path": str(resolved_model_path),
            }

        search_roots: tuple[Path, ...] = config.loading.iter_search_roots("model")
        for search_root in search_roots:
            try:
                resolved_model_path = self._resolve_model_file_path(search_root)
            except ConfigurationError:
                continue
            loaded_model = self._load_model_from_path(resolved_model_path)
            input_payload["model"] = loaded_model
            return loaded_model, {
                "source": "discover",
                "path": str(resolved_model_path),
                "search_roots": [str(root_path) for root_path in search_roots],
            }

        raise ConfigurationError(
            "Model resolution failed: set 'config.loading.model_object' or "
            "'config.loading.model_path' or provide at least one search root in "
            "'config.loading.search_roots'."
        )

    def _resolve_model_file_path(self, model_path: Path) -> Path:
        """Generated: validation needed.

        Description:
            Resolve a model file path from file or directory input.

        Args:
            model_path (Path): Candidate model file or directory path.

        Returns:
            Path: Resolved model file path.

        Raises:
            ConfigurationError: When no supported model file can be resolved.
        """

        if model_path.is_file():
            if model_path.suffix.lower() not in _ALLOWED_MODEL_SUFFIXES:
                raise ConfigurationError(
                    "Unsupported model file extension. Use one of: .json, .xml, .mat"
                )
            return model_path

        if model_path.is_dir():
            model_candidates = sorted(
                candidate
                for candidate in model_path.iterdir()
                if candidate.is_file()
                and candidate.name.lower().startswith("model")
                and candidate.suffix.lower() in _ALLOWED_MODEL_SUFFIXES
            )
            if not model_candidates:
                raise ConfigurationError(
                    f"No model file found in directory '{model_path}'. "
                    "Expected file starting with 'model' and extension .json/.xml/.mat."
                )
            return model_candidates[0]

        raise ConfigurationError(
            f"Model path does not exist or is unsupported: '{model_path}'."
        )

    def _load_model_from_path(self, model_path: Path) -> Model:
        """Generated: validation needed.

        Description:
            Load cobra model from path using extension-aware loader.

        Args:
            model_path (Path): Model file path.

        Returns:
            cobra.Model: Loaded cobra model.

        Raises:
            ConfigurationError: When loaded object is not a cobra model.
        """

        loaded_object = load_existing_file_based_on_extension(
            model_path,
            is_cobra_model=True,
        )
        if not isinstance(loaded_object, Model):
            raise ConfigurationError(
                f"Loaded object is not cobra.Model for path '{model_path}'."
            )
        return loaded_object
