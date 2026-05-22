"""Generated: validation needed.

Description:
    High-level protein-stage coordinator that delegates to expression, PTR,
    and proteomics submodules.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from VmaxBuilder.config.dataclasses import APIConfig
from VmaxBuilder.config.enums import ProteinSourceMode
from VmaxBuilder.config.validation import ConfigurationError
from VmaxBuilder.core.protocols import Scaffold
from VmaxBuilder.expression.implementation import DefaultExpressionImplementation
from VmaxBuilder.protein.proteomics_implementation import DefaultProteomicsImplementation
from VmaxBuilder.protein.ptr_implementation import DefaultPTRImplementation

_MODE_REQUIREMENTS: dict[ProteinSourceMode, dict[str, tuple[str, ...]]] = {
    ProteinSourceMode.EXPRESSION_PTR: {
        "required_inputs": ("expression", "ptr"),
        "ignored_option_groups": ("proteomics",),
    },
    ProteinSourceMode.PROTEOMICS: {
        "required_inputs": ("proteomics",),
        "ignored_option_groups": ("expression", "ptr"),
    },
}


class DefaultProteinStageCoordinator:
    """Generated: validation needed.

    Description:
        Coordinate protein-stage execution across expression, PTR,
        and proteomics sub-implementations.

    Args:
        expression_implementation (DefaultExpressionImplementation | None):
            Expression submodule override.
        ptr_implementation (DefaultPTRImplementation | None): PTR submodule override.
        proteomics_implementation (DefaultProteomicsImplementation | None):
            Proteomics submodule override.
    """

    def __init__(
        self,
        expression_implementation: DefaultExpressionImplementation | None = None,
        ptr_implementation: DefaultPTRImplementation | None = None,
        proteomics_implementation: DefaultProteomicsImplementation | None = None,
    ) -> None:
        self.expression_implementation = (
            expression_implementation or DefaultExpressionImplementation()
        )
        self.ptr_implementation = ptr_implementation or DefaultPTRImplementation()
        self.proteomics_implementation = (
            proteomics_implementation or DefaultProteomicsImplementation()
        )

    def run(self, scaffold: Scaffold, config: APIConfig) -> Scaffold:
        """Generated: validation needed.

        Description:
            Execute protein-stage flow and attach protein abundance artifact + metadata.

        Args:
            scaffold (Scaffold): Shared pipeline scaffold.
            config (APIConfig): Root API configuration.

        Returns:
            Scaffold: Updated scaffold.

        Raises:
            ConfigurationError: When required inputs are missing or source mode
                is unsupported.

        Modifies:
            scaffold["artifacts"] and scaffold["metadata"].
        """

        mode_requirements = self.get_mode_requirements(config.protein.source_mode)

        if config.protein.source_mode is ProteinSourceMode.EXPRESSION_PTR:
            protein_abundance, mode_metadata = self._run_expression_ptr_flow(scaffold, config)
        elif config.protein.source_mode is ProteinSourceMode.PROTEOMICS:
            protein_abundance, mode_metadata = self._run_proteomics_flow(scaffold, config)
        else:
            raise ConfigurationError(
                f"Unsupported protein source mode: {config.protein.source_mode!s}."
            )

        artifacts_payload = scaffold.setdefault("artifacts", {})
        metadata_payload = scaffold.setdefault("metadata", {})
        artifacts_payload["protein_abundance"] = protein_abundance
        metadata_payload["protein_stage"] = {
            "status": "implemented_placeholder",
            "source_mode": config.protein.source_mode.value,
            "run_target_transcript_gene_level": config.run_target_transcript_gene_level,
            "required_inputs": list(mode_requirements["required_inputs"]),
            "ignored_option_groups": list(mode_requirements["ignored_option_groups"]),
            **mode_metadata,
        }
        return scaffold

    @staticmethod
    def get_mode_requirements(source_mode: ProteinSourceMode) -> dict[str, tuple[str, ...]]:
        """Generated: validation needed.

        Description:
            Return mandatory inputs and ignored option groups for one protein
            implementation mode.

        Args:
            source_mode (ProteinSourceMode): Selected protein source mode.

        Returns:
            dict[str, tuple[str, ...]]: Requirements metadata for selected mode.
        """

        return _MODE_REQUIREMENTS[source_mode]

    def _run_expression_ptr_flow(
        self,
        scaffold: Scaffold,
        config: APIConfig,
    ) -> tuple[pd.DataFrame, dict[str, Any]]:
        """Generated: validation needed.

        Description:
            Build protein abundance from expression and PTR submodule outputs.

        Args:
            scaffold (Scaffold): Shared pipeline scaffold.
            config (APIConfig): Root API configuration.

        Returns:
            tuple[pd.DataFrame, dict[str, Any]]: Protein abundance and metadata.

        Raises:
            ConfigurationError: When expression or PTR input is missing.
        """

        expression_df = self.expression_implementation.resolve_expression_frame(
            scaffold,
            config,
        )
        if expression_df is None:
            raise ConfigurationError(
                "Expression input missing for protein.source_mode='expression_ptr'. "
                "Provide scaffold.inputs['expression'], "
                "config.loading.in_memory_inputs['expression'], "
                "or config.loading.expression_path."
            )

        expression_df = self.expression_implementation.prepare_expression_frame(
            expression_df,
            config,
        )
        ptr_df = self.ptr_implementation.resolve_ptr_frame(scaffold, config)
        if ptr_df is None:
            raise ConfigurationError(
                "PTR input missing for protein.source_mode='expression_ptr'. "
                "Provide scaffold.inputs['ptr'], config.loading.in_memory_inputs['ptr'], "
                "or config.loading.ptr_path."
            )

        protein_df = self.ptr_implementation.combine_expression_with_ptr(
            expression_df,
            ptr_df,
        )
        return protein_df, {
            "implementation": "expression_ptr",
            "expression_implementation": type(self.expression_implementation).__name__,
            "ptr_implementation": config.protein.ptr_method,
            "ptr_runtime_implementation": type(self.ptr_implementation).__name__,
            "ptr_used": True,
            "expression_id_type": config.expression.id_type,
            "expression_transformation_state": config.expression.transformation_state,
            "expression_origin_level": config.expression.origin_transcript_gene_level,
            "expression_data_type": config.expression.data_type,
            "expression_thresholding": config.expression.thresholding,
            "ptr_id_type": config.ptr.id_type,
            "ptr_transformation_state": config.ptr.transformation_state,
            "ptr_origin_level": config.ptr.origin_transcript_gene_level,
        }

    def _run_proteomics_flow(
        self,
        scaffold: Scaffold,
        config: APIConfig,
    ) -> tuple[pd.DataFrame, dict[str, Any]]:
        """Generated: validation needed.

        Description:
            Build protein abundance directly from proteomics with proteomics submodule.

        Args:
            scaffold (Scaffold): Shared pipeline scaffold.
            config (APIConfig): Root API configuration.

        Returns:
            tuple[pd.DataFrame, dict[str, Any]]: Protein abundance and metadata.

        Raises:
            ConfigurationError: When proteomics input is missing.
        """

        proteomics_df = self.proteomics_implementation.resolve_proteomics_frame(
            scaffold,
            config,
        )
        if proteomics_df is None:
            raise ConfigurationError(
                "Proteomics input missing for protein.source_mode='proteomics'. "
                "Provide scaffold.inputs['proteomics'], "
                "config.loading.in_memory_inputs['proteomics'], "
                "or config.loading.proteomics_path."
            )

        protein_df = self.proteomics_implementation.impute_proteomics(proteomics_df)
        return protein_df, {
            "implementation": "proteomics",
            "proteomics_implementation": type(self.proteomics_implementation).__name__,
            "proteomics_id_type": config.proteomics.id_type,
            "proteomics_origin_level": config.proteomics.origin_transcript_gene_level,
            "proteomics_transformation_state": config.proteomics.transformation_state,
            "imputation_strategy": config.proteomics.imputation_strategy,
            "fallback_imputation_strategy": config.proteomics.fallback_imputation_strategy,
        }
