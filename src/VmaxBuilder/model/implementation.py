from __future__ import annotations

from pathlib import Path
from typing import Any

from VmaxBuilder.config.dataclasses import APIConfig
from VmaxBuilder.config.validation import (
    ConfigurationError,
    validate_loading_policy,
    validate_model_config,
)
from VmaxBuilder.core.protocols import Scaffold


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

        model_reference = self._resolve_model_reference(config, scaffold)
        artifacts_payload = scaffold.setdefault("artifacts", {})
        metadata_payload = scaffold.setdefault("metadata", {})

        artifacts_payload["model_reference"] = model_reference
        metadata_payload["model_stage"] = {
            "reaction_notation": config.model.reaction_notation.value,
            "make_copy": config.model.make_copy,
        }
        return scaffold

    def _resolve_model_reference(
        self, config: APIConfig, scaffold: Scaffold
    ) -> dict[str, Any]:
        """Generated: validation needed.

        Description:
            Resolve model reference from explicit path or configured discovery roots.

        Args:
            config (APIConfig): Root API configuration.
            scaffold (Scaffold): Shared pipeline scaffold.

        Returns:
            dict[str, Any]: Model reference metadata payload.

        Raises:
            ConfigurationError: When explicit path and discovery roots are both absent.
        """

        input_payload = scaffold.setdefault("inputs", {})
        in_memory_inputs = config.loading.get_effective_in_memory_inputs()
        model_object = input_payload.get("model", in_memory_inputs.get("model"))
        if model_object is not None:
            input_payload["model"] = model_object
            return {
                "source": "in_memory",
                "object_type": type(model_object).__name__,
            }

        explicit_paths = config.loading.get_effective_exact_paths()
        model_path = explicit_paths.get("model")
        if model_path is not None:
            return {
                "source": "explicit_path",
                "path": str(model_path),
            }

        search_roots: tuple[Path, ...] = config.loading.iter_search_roots("model")
        if search_roots:
            return {
                "source": "discover",
                "search_roots": [str(root_path) for root_path in search_roots],
            }

        raise ConfigurationError(
            "Model resolution failed: set 'config.loading.model_object' or "
            "'config.loading.model_path' or provide at least one search root in "
            "'config.loading.search_roots'."
        )
