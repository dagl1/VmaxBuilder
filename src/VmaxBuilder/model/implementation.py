from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

import pandas as pd
from cobra import Model

from VmaxBuilder.config.dataclasses import APIConfig
from VmaxBuilder.config.validation import (
    ConfigurationError,
    validate_loading_policy,
    validate_model_config,
)
from VmaxBuilder.core.protocols import Scaffold
from VmaxBuilder.database_retrieval.identifier_translation import (
    IdentifierTranslationService,
)
from VmaxBuilder.model.preprocessing import preprocess_model
from VmaxBuilder.utils.file_handling import load_existing_file_based_on_extension


class TranscriptMetadataServiceProtocol(Protocol):
    """Generated: validation needed.

    Description:
        Protocol for model-stage transcript metadata lookup services.
    """

    def build_gene_transcript_dataframe(
        self,
        gene_ids: list[str],
        *,
        gene_id_type: str,
        species: str | None,
        provider: str,
        max_workers: int,
        batch_size: int,
    ) -> pd.DataFrame:
        """Generated: validation needed.

        Description:
            Build transcript metadata dataframe for one list of model genes.

        Args:
            gene_ids (list[str]): Model gene identifiers.
            gene_id_type (str): Gene identifier namespace.
            species (str | None): Optional species hint.
            provider (str): Translation provider key.
            max_workers (int): Maximum worker thread count.
            batch_size (int): Query batch size.

        Returns:
            pd.DataFrame: Transcript metadata dataframe.
        """


class DefaultModelStageImplementation:
    """Generated: validation needed.

    Description:
        Validate model/loading configuration and resolve model input reference.

    Raises:
        ConfigurationError: When model resolution input is missing.

    Modifies:
        scaffold payload for model stage artifacts and metadata.
    """

    def __init__(
        self,
        translation_service: TranscriptMetadataServiceProtocol | None = None,
    ) -> None:
        """Generated: validation needed.

        Description:
            Initialize model-stage implementation dependencies.

        Args:
            translation_service (TranscriptMetadataServiceProtocol | None): Optional
                transcript metadata lookup service override.
        """

        self._translation_service = translation_service or IdentifierTranslationService()

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
        if config.run_target_transcript_gene_level.lower() == "transcript":
            transcript_artifacts = self._build_transcript_artifacts_for_model(
                model=preprocessing_result["irreversible_model"],
                config=config,
            )
            artifacts_payload.update(transcript_artifacts)
        metadata_payload["model_stage"] = {
            "reaction_notation": config.model.reaction_notation.value,
            "make_copy": config.model.make_copy,
        }
        return scaffold

    def _build_transcript_artifacts_for_model(
        self,
        *,
        model: Model,
        config: APIConfig,
    ) -> dict[str, Any]:
        """Generated: validation needed.

        Description:
            Build transcript metadata artifacts for model genes when transcript
            target level is requested.

        Args:
            model (Model): Irreversible cobra model.
            config (APIConfig): Root API configuration.

        Returns:
            dict[str, Any]: Transcript metadata and mapping artifacts.
        """

        genes_in_model = [gene.id for gene in model.genes]
        model_id_type = self._build_id_type_name(config.model.id_type, config.model.level)
        if model_id_type is None:
            transcript_df = pd.DataFrame(
                columns=[
                    "transcript_id",
                    "gene_id",
                    "is_protein_coding",
                    "is_canonical",
                    "peptide_len",
                    "cdna_len",
                    "peptide_seq",
                    "cdna_seq",
                ]
            )
        else:
            transcript_df = self._translation_service.build_gene_transcript_dataframe(
                genes_in_model,
                gene_id_type=model_id_type,
                species=config.transcript_processing.id_translation_species,
                provider=config.transcript_processing.id_translation_provider,
                max_workers=config.transcript_processing.id_translation_max_workers,
                batch_size=config.transcript_processing.id_translation_batch_size,
            )

        transcript_to_gene_mapping = transcript_df.set_index("transcript_id")[
            "gene_id"
        ].to_dict()
        gene_to_transcript_mapping = (
            transcript_df.groupby("gene_id")["transcript_id"].agg(list).to_dict()
            if not transcript_df.empty
            else {}
        )
        protein_coding_transcripts = transcript_df[transcript_df["is_protein_coding"]][
            "transcript_id"
        ].tolist()
        canonical_transcripts = transcript_df[transcript_df["is_canonical"]][
            "transcript_id"
        ].tolist()
        transcript_sequences = transcript_df[
            [
                "transcript_id",
                "gene_id",
                "peptide_len",
                "cdna_len",
                "peptide_seq",
                "cdna_seq",
            ]
        ]

        return {
            "gene_transcript_mapping": transcript_df,
            "transcript_to_gene_mapping": transcript_to_gene_mapping,
            "gene_to_transcript_mapping": gene_to_transcript_mapping,
            "protein_coding_transcripts": protein_coding_transcripts,
            "canonical_transcripts": canonical_transcripts,
            "transcript_sequences": transcript_sequences,
            "genes_in_model": genes_in_model,
        }

    @staticmethod
    def _build_id_type_name(provider: str | None, level: str) -> str | None:
        """Generated: validation needed.

        Description:
            Build full identifier type name from provider and granularity level.

        Args:
            provider (str | None): Identifier provider value.
            level (str): Gene/transcript level.

        Returns:
            str | None: Full identifier type name or None when provider missing.
        """

        if provider is None:
            return None
        level_lower = level.lower()
        if provider == "ensembl":
            return f"ensembl_{level_lower}_id"
        return provider

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
            resolved_model_path = self._resolve_model_file_path(model_path, config)
            loaded_model = self._load_model_from_path(resolved_model_path)
            input_payload["model"] = loaded_model
            return loaded_model, {
                "source": "explicit_path",
                "path": str(resolved_model_path),
            }

        search_roots: tuple[Path, ...] = config.loading.iter_search_roots("model")
        for search_root in search_roots:
            try:
                resolved_model_path = self._resolve_model_file_path(search_root, config)
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

    def _resolve_model_file_path(self, model_path: Path, config: APIConfig) -> Path:
        """Generated: validation needed.

        Description:
            Resolve a model file path from file or directory input.

        Args:
            model_path (Path): Candidate model file or directory path.
            config (APIConfig): Root API configuration.

        Returns:
            Path: Resolved model file path.

        Raises:
            ConfigurationError: When no supported model file can be resolved.
        """

        allowed_extensions = {
            extension.lower()
            for extension in config.loading.get_discovery_extensions("model")
        }
        filename_prefixes = tuple(
            prefix.lower() for prefix in config.loading.get_discovery_prefixes("model")
        )

        if model_path.is_file():
            if model_path.suffix.lower() not in allowed_extensions:
                raise ConfigurationError(
                    "Unsupported model file extension. "
                    "Use configured model discovery_extensions."
                )
            return model_path

        print(f" model path is {model_path}, is_dir = {model_path.is_dir()}")
        if model_path.is_dir():
            model_candidates = sorted(
                candidate
                for candidate in model_path.iterdir()
                if candidate.is_file()
                and candidate.name.lower().startswith(filename_prefixes)
                and candidate.suffix.lower() in allowed_extensions
            )
            if not model_candidates:
                raise ConfigurationError(
                    f"No model file found in directory '{model_path}'. "
                    "Expected file matching configured model discovery_prefixes and "
                    "discovery_extensions."
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
