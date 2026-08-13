from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np
from cobra.core.model import Model

from VmaxBuilder.base.classes import BaseImplementation, DiagnosticOutputSpec
from VmaxBuilder.base.configs import FullConfig, InputSpec, OutputSpec, Scaffold
from VmaxBuilder.GPR.gpr_preprocessing import (
    build_gene_to_IFP_mapping,
    build_gene_to_transcripts_mapping,
    build_IFP_mapping_from_gpr_rules,
    build_reaction_to_IFP_mapping,
    clear_simplification_cache,
    expand_gene_IFP_to_transcript_IFPs,
    get_simplification_cache_info,
    get_unique_genes_from_IFP_mapping,
    get_unique_gpr_rules,
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
            scaffold_location="artifacts",
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

        gpr_rule_diagnostics = self.diagnose_gpr_rules(
            gpr_rules,
        )
        gpr_rule_diagnostic_spec = DiagnosticOutputSpec(
            data=gpr_rule_diagnostics,
            save_file_name="gpr_rule_diagnostics",
            extensions=".json",
            data_type=dict,
        )
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
        self.logger.warning(
            f"Missing genes from model: {missing_genes_from_model}. "
            f"Missing genes from IFP mapping: {missing_genes_from_IFP_mapping}. "
            f"These are likely genes without any reactions associated "
        )

        (elapsed_time_2, gene_to_IFP_mapping) = self.get_time_decorator(
            build_gene_to_IFP_mapping
        )(IFP_mapping)
        (elapsed_time_3, reaction_to_IFP_mapping) = self.get_time_decorator(
            build_reaction_to_IFP_mapping
        )(IFP_mapping, cobra_model)

        artifacts_payload = {}
        metadata_payload = {}

        elapsed_time_4 = 0
        transcript_metadata_payload = {}
        transcript_diagnostics_payload = {}
        if self.full_config.run.run_target_transcript_gene_level.lower() == "transcript":
            # todo:
            (
                elapsed_time_4,
                (
                    IFP_mapping,
                    artifacts_payload,
                    transcript_metadata_payload,
                    transcript_diagnostics_payload,
                ),
            ) = self.get_time_decorator(self._convert_gene_IFP_to_transcript_IFP)(
                cobra_model,
                IFP_mapping=IFP_mapping,
                config=self.full_config,
            )
        elapsed_time = elapsed_time + elapsed_time_2 + elapsed_time_3 + elapsed_time_4
        metadata_payload = self.create_metadata(
            elapsed_time=elapsed_time, additional_metadata=metadata_payload
        )
        metadata = {**transcript_metadata_payload, **metadata_payload}

        artifacts = {
            "IFP_mapping": IFP_mapping,
            "gene_to_IFP_mapping": gene_to_IFP_mapping,
            "reaction_to_IFP_mapping": reaction_to_IFP_mapping,
            **artifacts_payload,
        }
        diagnostics = {
            "gpr": gpr_rule_diagnostic_spec,
            **transcript_diagnostics_payload,
        }

        self.logger.debug(f"Generated IFP mapping for {len(IFP_mapping)} GPR rules.")

        return {
            "outputs": {},
            "artifacts": artifacts,
            "metadata": metadata,
            "diagnostics": diagnostics,
        }

    def diagnose_gpr_rules(
        self,
        gpr_rules: dict[str, list[str]],
    ) -> dict[str, Any]:
        total_gpr_rules = len(gpr_rules)

        # A reaction should normally occur under only one GPR rule,
        # but use a set in case the input contains duplicates.
        all_reactions = {
            reaction for reactions in gpr_rules.values() for reaction in reactions
        }

        total_reactions = len(all_reactions)

        # IMPORTANT:
        # This assumes the GPR rule is whitespace-tokenized.
        # If your GPR rules contain "and"/"or", replace this with
        # your actual GPR parser.
        genes_per_rule = {gpr_rule: len(gpr_rule.split()) for gpr_rule in gpr_rules}

        gene_counts = np.asarray(
            list(genes_per_rule.values()),
            dtype=float,
        )

        reactions_per_rule = {
            gpr_rule: len(set(reactions)) for gpr_rule, reactions in gpr_rules.items()
        }

        reaction_counts = np.asarray(
            list(reactions_per_rule.values()),
            dtype=float,
        )

        def summarize(values: np.ndarray) -> dict[str, float]:
            q25, median, q75 = np.percentile(
                values,
                [25, 50, 75],
            )

            return {
                "min": float(np.min(values)),
                "q25": float(q25),
                "median": float(median),
                "q75": float(q75),
                "max": float(np.max(values)),
                "mean": float(np.mean(values)),
                "iqr": float(q75 - q25),
            }

        rules_by_reaction_count = Counter(reactions_per_rule.values())
        single_reaction_rules = sum(count == 1 for count in reactions_per_rule.values())
        shared_rules = sum(count > 1 for count in reactions_per_rule.values())

        # Fraction of reactions belonging to shared rules
        shared_reactions = sum(count for count in reactions_per_rule.values() if count > 1)

        most_shared_gpr_rules = [
            {
                "gpr_rule": gpr_rule,
                "reaction_count": len(set(gpr_rules[gpr_rule])),
                "reactions": list(set(gpr_rules[gpr_rule])),
            }
            for gpr_rule, _ in sorted(
                reactions_per_rule.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:20]
        ]

        sorted_reaction_counts = np.sort(reaction_counts)[::-1]
        cumulative_fraction = np.cumsum(sorted_reaction_counts) / np.sum(
            sorted_reaction_counts
        )

        # Helper: fraction of reactions covered by top N rules
        def top_n_fraction(n: int) -> float:
            if len(sorted_reaction_counts) == 0:
                return 0.0

            n = min(n, len(sorted_reaction_counts))

            return float(np.sum(sorted_reaction_counts[:n]) / np.sum(sorted_reaction_counts))

        return {
            "total_gpr_rules": total_gpr_rules,
            "total_reactions": total_reactions,
            "genes_per_gpr_rule": summarize(gene_counts),
            "reactions_per_gpr_rule": summarize(reaction_counts),
            "rules_by_reaction_count": dict(sorted(rules_by_reaction_count.items())),
            "single_reaction_rules": single_reaction_rules,
            "shared_gpr_rules": shared_rules,
            "fraction_gpr_rules_used_by_one_reaction": (
                single_reaction_rules / total_gpr_rules
            ),
            "fraction_gpr_rules_shared": (shared_rules / total_gpr_rules),
            "fraction_reactions_using_shared_gpr_rules": (
                shared_reactions / total_reactions if total_reactions > 0 else 0.0
            ),
            "top_n_reaction_fraction": {
                "top_1": top_n_fraction(1),
                "top_5": top_n_fraction(5),
                "top_10": top_n_fraction(10),
                "top_25": top_n_fraction(25),
                "top_50": top_n_fraction(50),
            },
            "most_shared_gpr_rules": most_shared_gpr_rules,
            "cumulative_fraction_of_reactions_by_top_n_rules": {
                "top_1": float(cumulative_fraction[0])
                if len(cumulative_fraction) > 0
                else 0.0,
                "top_5": float(cumulative_fraction[4])
                if len(cumulative_fraction) > 4
                else 0.0,
                "top_10": float(cumulative_fraction[9])
                if len(cumulative_fraction) > 9
                else 0.0,
                "top_25": float(cumulative_fraction[24])
                if len(cumulative_fraction) > 24
                else 0.0,
                "top_50": float(cumulative_fraction[49])
                if len(cumulative_fraction) > 49
                else 0.0,
            },
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
        diagnostics_payload = {}
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
        diagnostics_payload = {
            "gpr_transcript_mapping": {"transcript_IFP_complexity_skips": complexity_skips}
        }

        artifacts_payload["transcript_IFP_complexity_report"] = complexity_skips
        return (
            transcript_level_mapping,
            artifacts_payload,
            metadata_payload,
            diagnostics_payload,
        )

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
    allocation_stage_loading_info = StageLoadingInfo(
        stage_name="allocation",
    )

    # Protein inputs (set whichever mode needs).
    stage_loading_info = StageLoading(
        model_loading_info=model_stage_loading_info,
        protein_loading_info=protein_stage_loading_info,
        allocation_loading_info=allocation_stage_loading_info,
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
