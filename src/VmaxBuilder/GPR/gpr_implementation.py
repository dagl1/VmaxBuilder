"""Generated: validation needed.

Description:
    GPR stage implementation for deriving independently functioning protein
    (IFP) complex mappings for model workflows.
"""

from __future__ import annotations

from typing import Any

from cobra.core.model import Model

from VmaxBuilder.base.classes import BaseImplementation
from VmaxBuilder.base.configs import FullConfig, InputSpec, OutputSpec, Scaffold
from VmaxBuilder.GPR.gpr_preprocessing import (
    build_gene_to_transcripts_mapping,
    build_IFP_mapping_from_gpr_rules,
    clear_simplification_cache,
    expand_gene_IFP_to_transcript_IFPs,
    get_simplification_cache_info,
    get_unique_genes_from_IFP_mapping,
    get_unique_gpr_rules,
    simplify_gpr_rule,
)


class DefaultGPRImplementation(BaseImplementation[FullConfig]):
    STAGE_NAME: str = "model"
    IMPL_NAME: str = "default_gpr"
    INPUTS: list[InputSpec] = [
        InputSpec(
            name="irreversible_cobra_model",
            data_type=Model,
            in_scaffold=True,
        ),
    ]
    OUTPUTS: list[OutputSpec] = [
        OutputSpec(
            name="IFP_mapping",
            data_type=dict,
            scaffold_location="outputs",
            save_file_name="IFP_mapping",
            extension=".json",
            validator=None,
        ),
        OutputSpec(
            name="gene_to_IFP_mapping",
            data_type=dict,
            scaffold_location="artifacts",
            save_file_name="gene_to_IFP_mapping",
            extension=".json",
            validator=None,
        ),
        OutputSpec(
            name="reaction_to_IFP_mapping",
            data_type=dict,
            scaffold_location="artifacts",
            save_file_name="reaction_to_IFP_mapping",
            extension=".json",
            validator=None,
        ),
    ]

    # BASE_STAGE_CONFIG: type | None = None
    # IMPLEMENTATION_CONFIG_CLASS: type | None = None
    # _RESOLVED_CONFIG_CLASS: type | None = None
    # INPUTS: list["InputSpec"] = []
    # OUTPUTS: list["OutputSpec"] = []
    # CHILD_IMPLEMENTATIONS: list[type["BaseImplementation"]] = []
    # DIAGNOSTICS: list[ImplementationDiagnostics] = []

    """Generated: validation needed.

    Description:
        GPR simplification scaffold for deriving gene-level IFP mappings.
    """

    def generate_outputs(self, scaffold: Scaffold) -> dict[str, Any]:
        """Generated: validation needed.

        Description:
            Build simplified gene-level IFPs for each unique model GPR rule and
            attach reaction<->IFP indexes to scaffold artifacts.

        Args:
            scaffold (Scaffold): Shared pipeline scaffold.
            config (FullConfig): Root API configuration.

        Returns:
            dict[str, Any]: IFP mapping payload.

        Modifies:
            scaffold artifacts and metadata payloads.
        """

        cobra_model = scaffold.get_scaffold_value("irreversible_cobra_model")
        if cobra_model is None:
            raise ValueError("No COBRA model found in scaffold for GPR processing.")
        gpr_rules = get_unique_gpr_rules(cobra_model)
        (elapsed_time, IFP_mapping) = self.get_time_decorator(
            build_IFP_mapping_from_gpr_rules
        )(gpr_rules)
        model_genes = set(gene.id for gene in cobra_model.genes)
        missing_genes_from_model = (
            get_unique_genes_from_IFP_mapping(IFP_mapping) - model_genes
        )
        missing_genes_from_IFP_mapping = model_genes - get_unique_genes_from_IFP_mapping(
            IFP_mapping
        )
        self.logger.error(
            f"Missing genes from model: {missing_genes_from_model}. "
            f"Missing genes from IFP mapping: {missing_genes_from_IFP_mapping}."
        )

        (elapsed_time_2, gene_to_IFP_mapping) = self.get_time_decorator(
            self.build_gene_to_IFP_mapping
        )(IFP_mapping)
        (elapsed_time_3, reaction_to_IFP_mapping) = self.get_time_decorator(
            self.build_reaction_to_IFP_mapping
        )(IFP_mapping)

        artifacts_payload = {}
        metadata_payload = {}
        diagnostics_payload = {}
        elapsed_time_4 = 0
        if self.full_config.run.run_target_transcript_gene_level.lower() == "transcript":
            # todo:
            (
                elapsed_time_4,
                (
                    IFP_mapping,
                    artifacts_payload,
                    metadata_payload,
                    diagnostics_payload,
                ),
            ) = self.get_time_decorator(self._convert_gene_IFP_to_transcript_IFP)(
                cobra_model,
                IFP_mapping=IFP_mapping,
                config=self.full_config,
            )
        elapsed_time = elapsed_time + elapsed_time_2 + elapsed_time_3 + elapsed_time_4
        artifacts = {
            "gene_to_IFP_mapping": gene_to_IFP_mapping,
            "reaction_to_IFP_mapping": reaction_to_IFP_mapping,
            **artifacts_payload,
        }

        metadata_payload = self.create_metadata(
            elapsed_time=elapsed_time, additional_metadata=metadata_payload
        )
        self.logger.debug(f"Generated IFP mapping for {len(IFP_mapping)} GPR rules.")

        return {
            "outputs": {
                "IFP_mapping": IFP_mapping,
            },
            "artifacts": artifacts,
            "metadata": metadata_payload,
            "diagnostics": diagnostics_payload,
        }

    def create_metadata(
        self,
        elapsed_time: float | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        metadata_payload = kwargs.get("additional_metadata", {})

        metadata_payload = {
            **metadata_payload,
            "gpr": {
                "implementation": type(self).__name__,
                "elapsed_time_seconds": elapsed_time,
                "status": "implemented_gene_rule_simplifier",
                "cache_info": self.get_simplification_cache_info(),
                "params": self.get_implementation_config_params(),
            },
        }
        return metadata_payload

    def build_gene_to_IFP_mapping(
        self,
        IFP_mapping: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, list[str]]]:
        gene_to_IFP_mapping: dict[str, dict[str, list[str]]] = {}
        for gpr_rule, _IFP_mapping in IFP_mapping.items():
            for IFP_payload in _IFP_mapping.get("IFP_objects", []):
                IFP = IFP_payload.get("IFP")
                genes_in_IFP = IFP_payload.get("genes_in_IFP", [])
                for gene in genes_in_IFP:
                    gene_to_IFP_mapping[gene] = {
                        "IFPs": gene_to_IFP_mapping.get(gene, {}).get("IFPs", []) + [IFP],
                        "reactions_with_gene": gene_to_IFP_mapping.get(gene, {}).get(
                            "reactions_with_IFP", []
                        ),
                        "gpr_rules_with_gene": gene_to_IFP_mapping.get(gene, {}).get(
                            "gpr_rules_with_gene", []
                        )
                        + [gpr_rule],
                    }

        for _, mapping in gene_to_IFP_mapping.items():
            mapping["IFPs"] = sorted(set(mapping["IFPs"]))
            mapping["reactions_with_gene"] = sorted(set(mapping["reactions_with_gene"]))
            mapping["gpr_rules_with_gene"] = sorted(set(mapping["gpr_rules_with_gene"]))

        return gene_to_IFP_mapping

    def build_reaction_to_IFP_mapping(
        self,
        IFP_mapping: dict[str, dict[str, Any]],
    ):
        reaction_to_IFP_mapping: dict[str, dict[str, list[str]]] = {}
        for gpr_rule, _IFP_mapping in IFP_mapping.items():
            for IFP_payload in _IFP_mapping.get("IFP_objects", []):
                IFP = IFP_payload.get("IFP")
                reactions_with_IFP = IFP_payload.get("reactions_with_IFP", [])
                for reaction in reactions_with_IFP:
                    reaction_to_IFP_mapping[reaction] = {
                        "IFPs": reaction_to_IFP_mapping.get(reaction, {}).get("IFPs", [])
                        + [IFP],
                        "gpr_rules": reaction_to_IFP_mapping.get(reaction, {}).get(
                            "gpr_rules", []
                        )
                        + [gpr_rule],
                        "genes": reaction_to_IFP_mapping.get(reaction, {}).get("genes", []),
                    }

        for _, mapping in reaction_to_IFP_mapping.items():
            mapping["IFPs"] = sorted(set(mapping["IFPs"]))
            mapping["gpr_rules"] = sorted(set(mapping["gpr_rules"]))
            mapping["genes"] = sorted(set(mapping["genes"]))

        return reaction_to_IFP_mapping

    def _convert_gene_IFP_to_transcript_IFP(
        self,
        cobra_model: Model,
        *,
        IFP_mapping: dict[str, Any],
        config: FullConfig,
    ) -> tuple[
        dict[str, Any],
        dict[str, Any],
        dict[str, Any],
        dict[str, Any],
    ]:
        """Generated: validation needed.

        Description:
            Convert each gene-level IFP into transcript-level IFPs using scaffold
            gene->transcript mapping artifacts.

        Args:
            scaffold (Scaffold): Shared pipeline scaffold.
            IFP_mapping (dict[str, Any]): Per-rule gene-level IFP payload.
            config (FullConfig): Root API configuration containing expansion limit.

        Returns:
            dict[str, Any]: Transcript-level IFP mapping payload.

        Modifies:
            scaffold metadata, diagnostics, and artifacts payloads.
        """

        artifacts_payload = {}
        metadata_payload = {}
        diagnostics_payload = {"model_stage": {"gpr": {}}}
        mapping_artifact = artifacts_payload.get("gene_transcript_mapping")
        if mapping_artifact is None:
            mapping_artifact = artifacts_payload.get("transcript_gene_map")

        gene_to_transcripts = build_gene_to_transcripts_mapping(mapping_artifact)
        if not gene_to_transcripts:
            metadata_payload.setdefault("gpr", {})["transcript_IFP_conversion"] = (
                "skipped_missing_gene_transcript_mapping"
            )
            return (
                IFP_mapping,
                artifacts_payload,
                metadata_payload,
                diagnostics_payload,
            )

        rule_to_reactions: dict[str, list[str]] = {}
        if cobra_model is not None:
            for reaction in cobra_model.reactions:
                reaction_rule = reaction.gene_reaction_rule.strip()
                if reaction_rule:
                    rule_to_reactions.setdefault(reaction_rule, []).append(reaction.id)

        complexity_skips: list[dict[str, Any]] = []

        transcript_level_mapping: dict[str, Any] = {}
        for gpr_rule, payload in IFP_mapping.items():
            gene_IFPs = [str(IFP) for IFP in payload.get("simplified_gene_IFPs", [])]
            transcript_IFPs: set[str] = set()

            for gene_IFP in gene_IFPs:
                expansion_outcome = expand_gene_IFP_to_transcript_IFPs(
                    gene_IFP,
                    gene_to_transcripts,
                    maximum_expansion=(config.model.maximum_transcript_IFP_expansion),
                )

                if bool(expansion_outcome["exceeded_threshold"]):
                    complexity_skips.append(
                        {
                            "gene_IFP": gene_IFP,
                            "maximum_transcript_IFP_expansion": (
                                config.maximum_transcript_IFP_expansion  # ty: ignore[unresolved-attribute] # noqa
                            ),
                            "actual_expansion_count": int(
                                expansion_outcome["expansion_count"]
                            ),
                            "transcripts_used_by_gene": expansion_outcome[
                                "transcripts_used_by_gene"
                            ],
                            "affected_reactions": sorted(rule_to_reactions.get(gpr_rule, [])),
                            "fallback": "kept_gene_level_IFP",
                        }
                    )
                    transcript_IFPs.add(gene_IFP)
                    continue

                transcript_IFPs.update(
                    str(transcript_IFP)
                    for transcript_IFP in expansion_outcome["transcript_IFPs"]
                )

            transcript_level_mapping[gpr_rule] = {
                **payload,
                "simplified_gene_IFPs": sorted(transcript_IFPs),
                "transcript_expansion_count": len(transcript_IFPs),
            }

        metadata_payload.setdefault("gpr", {})["transcript_IFP_conversion"] = {
            "status": "applied",
            "rules_converted": len(transcript_level_mapping),
            "gene_transcript_mapping_genes": len(gene_to_transcripts),
            "maximum_transcript_IFP_expansion": (
                config.model.maximum_transcript_IFP_expansion
            ),
            "complexity_skips": len(complexity_skips),
        }
        diagnostics_payload["model_stage"]["gpr"]["transcript_IFP_complexity_skips"] = (
            complexity_skips
        )
        artifacts_payload["transcript_IFP_complexity_report"] = complexity_skips
        return (
            transcript_level_mapping,
            artifacts_payload,
            metadata_payload,
            diagnostics_payload,
        )

    def _simplify_gpr_rule(self, gpr_rule: str) -> list[str]:
        """Generated: validation needed.

        Description:
            Simplify one GPR rule into DNF-style `and` IFPs.

        Args:
            gpr_rule (str): Raw GPR rule.

        Returns:
            list[str]: Simplified IFPs.
        """

        return simplify_gpr_rule(gpr_rule)

    @staticmethod
    def clear_simplification_cache() -> None:
        """Generated: validation needed.

        Description:
            Clear parser/simplification cache for deterministic benchmarking.
        """

        clear_simplification_cache()

    @staticmethod
    def get_simplification_cache_info() -> dict[str, int]:
        """Generated: validation needed.

        Description:
            Return cache statistics for rule simplification.

        Returns:
            dict[str, int]: Cache statistics dictionary.
        """

        return get_simplification_cache_info()


if __name__ == "__main__":
    from pathlib import Path

    from VmaxBuilder.base.configs import RunConfig, StageLoading, StageLoadingInfo
    from VmaxBuilder.base.orchestrator import Orchestrator
    from VmaxBuilder.stages.model.default.implementation import (
        DefaultIrreversibleModelImplementation,
    )
    from VmaxBuilder.stages.protein.MvalueTrimmingExpressionPTR.implementation import (
        MvalueTrimmingExpressionPTRImplementation,
    )

    base_dir = Path("~/git/SWAPAM/data/for_SWAMP/")
    models_dir = base_dir / "models"
    model_name = "model_inhouse_v7_human"
    model_dir = models_dir / model_name
    model_path = model_dir

    expression_path = base_dir / "expression_datasets" / "NCI_60_human"
    ptr_path = base_dir / "PTR_datasets" / "Eraslan2019_human"
    # proteomics_path = base_dir / "proteomics" / "NCI60"
    output_path = Path("~/git/VmaxBuilder/data/run_example_output")
    create_dynamically_named_results = False
    model_stage_loading_info = StageLoadingInfo(
        stage_name="model",
        directories=model_dir,
        file_paths={
            "smiles_df": model_dir / "smiles_df.csv",
            "transcript_df": model_dir / "transcript_df.csv",
        },
    )
    protein_stage_loading_info = StageLoadingInfo(
        stage_name="protein",
        directories=[
            expression_path,
            ptr_path,
        ],
    )

    # Protein inputs (set whichever mode needs).
    stage_loading_info = StageLoading(
        model_loading_info=model_stage_loading_info,
        protein_loading_info=protein_stage_loading_info,
    )

    run_config = RunConfig(
        output_dir=output_path,
        run_name="test_model_implementation",
        create_dynamically_named_results=create_dynamically_named_results,
        # print_level="DEBUG",
    )

    orchestrator = Orchestrator(stage_loading_info, run_config)
    orchestrator.set_print_level("WARNING")
    model = orchestrator.set_model_implementation(DefaultIrreversibleModelImplementation)
    protein = orchestrator.set_protein_implementation(
        MvalueTrimmingExpressionPTRImplementation
    )

    protein.config.expression_sample_type_map = {idx: "heart" for idx in range(1, 1000)}
    protein.config.PTR_special_gene_groups = {"transport_reactions": []}
    protein.config.use_special_groups_for_unobserved_imputation = True

    orchestrator.return_config(verbose=False)
    orchestrator.config.run.overwrite_existing_results = True
    orchestrator.config.run.lazy_load = True

    orchestrator._discover_user_submitted_paths()
    orchestrator.config.run.paths._create_dirs()
    orchestrator.logger.info("Starting orchestrator run...")
    orchestrator._run_stage("model")
