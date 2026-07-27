"""Generated: validation needed.

Description:
    GPR stage implementation for deriving independently functioning protein
    (IFP) complex mappings for model workflows.
"""

from __future__ import annotations

from typing import Any

from cobra.core.model import Model

from VmaxBuilder.base.classes import BaseImplementation
from VmaxBuilder.base.configs import FullConfig, Scaffold
from VmaxBuilder.GPR.gpr_preprocessing import (
    build_gene_to_transcripts_mapping,
    build_ifp_mapping_from_gpr_rules,
    build_reaction_ifp_indexes,
    clear_simplification_cache,
    expand_gene_ifp_to_transcript_ifps,
    get_simplification_cache_info,
    get_unique_gpr_rules,
    simplify_gpr_rule,
)


class DefaultGPRImplementation(BaseImplementation[FullConfig]):
    STAGE_NAME: str = "model"
    IMPL_NAME: str = "default_gpr"

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

        cobra_model = scaffold.get_scaffold_value("cobra_model")
        if cobra_model is None:
            raise ValueError("No COBRA model found in scaffold for GPR processing.")
        gpr_rules = get_unique_gpr_rules(cobra_model)
        (elapsed_time, ifp_mapping) = self.get_time_decorator(
            self._convert_gene_gpr_rules_to_ifp
        )(gpr_rules)
        artifacts_payload = {}
        metadata_payload = {}
        diagnostics_payload = {}
        if self.full_config.run.run_target_transcript_gene_level.lower() == "transcript":
            (
                ifp_mapping,
                artifacts_payload,
                metadata_payload,
                diagnostics_payload,
            ) = self._convert_gene_ifp_to_transcript_ifp(
                cobra_model,
                ifp_mapping=ifp_mapping,
                config=self.full_config,
            )
        artifacts_IFP_payload = self._assign_ifps_to_reactions(cobra_model, ifp_mapping)
        artifact_payload = {**artifacts_payload, **artifacts_IFP_payload}
        metadata_payload = self.create_metadata(
            elapsed_time=elapsed_time, additional_metadata=metadata_payload
        )
        self.logger.debug(f"Generated IFP mapping for {len(ifp_mapping)} GPR rules.")

        return {
            "outputs": {"ifp_mapping": ifp_mapping},
            "artifacts": artifact_payload,
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

    def _assign_ifps_to_reactions(
        self,
        cobra_model: Model,
        ifp_mapping: dict[str, Any],
    ) -> dict[str, Any]:
        """Generated: validation needed.

        Description:
            Assign bidirectional reaction<->IFP indexes into scaffold artifacts.

        Args:
            scaffold (Scaffold): Shared pipeline scaffold.
            ifp_mapping (dict[str, Any]): Mapping of GPR rules to IFP payloads.

        Returns:
            Scaffold: Updated scaffold with reaction/IFP indexes.

        Modifies:
            scaffold artifacts payload.
        """

        artifacts_payload = {}

        reaction_to_ifps, ifp_to_reactions = build_reaction_ifp_indexes(
            model=cobra_model,
            ifp_mapping=ifp_mapping,
        )
        artifacts_payload["reaction_to_ifps"] = reaction_to_ifps
        artifacts_payload["ifp_to_reactions"] = ifp_to_reactions
        return artifacts_payload

    def _convert_gene_ifp_to_transcript_ifp(
        self,
        cobra_model: Model,
        *,
        ifp_mapping: dict[str, Any],
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
            ifp_mapping (dict[str, Any]): Per-rule gene-level IFP payload.
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
            metadata_payload.setdefault("gpr", {})["transcript_ifp_conversion"] = (
                "skipped_missing_gene_transcript_mapping"
            )
            return (
                ifp_mapping,
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
        for gpr_rule, payload in ifp_mapping.items():
            gene_ifps = [str(ifp) for ifp in payload.get("simplified_gene_ifps", [])]
            transcript_ifps: set[str] = set()

            for gene_ifp in gene_ifps:
                expansion_outcome = expand_gene_ifp_to_transcript_ifps(
                    gene_ifp,
                    gene_to_transcripts,
                    maximum_expansion=(config.model.maximum_transcript_ifp_expansion),
                )

                if bool(expansion_outcome["exceeded_threshold"]):
                    complexity_skips.append(
                        {
                            "gene_ifp": gene_ifp,
                            "maximum_transcript_ifp_expansion": (
                                config.maximum_transcript_ifp_expansion  # ty: ignore[unresolved-attribute] # noqa
                            ),
                            "actual_expansion_count": int(
                                expansion_outcome["expansion_count"]
                            ),
                            "transcripts_used_by_gene": expansion_outcome[
                                "transcripts_used_by_gene"
                            ],
                            "affected_reactions": sorted(rule_to_reactions.get(gpr_rule, [])),
                            "fallback": "kept_gene_level_ifp",
                        }
                    )
                    transcript_ifps.add(gene_ifp)
                    continue

                transcript_ifps.update(
                    str(transcript_ifp)
                    for transcript_ifp in expansion_outcome["transcript_ifps"]
                )

            transcript_level_mapping[gpr_rule] = {
                **payload,
                "simplified_gene_ifps": sorted(transcript_ifps),
                "transcript_expansion_count": len(transcript_ifps),
            }

        metadata_payload.setdefault("gpr", {})["transcript_ifp_conversion"] = {
            "status": "applied",
            "rules_converted": len(transcript_level_mapping),
            "gene_transcript_mapping_genes": len(gene_to_transcripts),
            "maximum_transcript_ifp_expansion": (
                config.model.maximum_transcript_ifp_expansion
            ),
            "complexity_skips": len(complexity_skips),
        }
        diagnostics_payload["model_stage"]["gpr"]["transcript_ifp_complexity_skips"] = (
            complexity_skips
        )
        artifacts_payload["transcript_ifp_complexity_report"] = complexity_skips
        return (
            transcript_level_mapping,
            artifacts_payload,
            metadata_payload,
            diagnostics_payload,
        )

    def _convert_gene_gpr_rules_to_ifp(self, gpr_rules: set[str]) -> dict[str, Any]:
        """Generated: validation needed.

        Description:
            Convert unique GPR rules into simplified gene IFPs.

        Args:
            gpr_rules (set[str]): Unique GPR rules.

        Returns:
            dict[str, Any]: Per-rule simplified IFPs and expansion count.
        """

        return build_ifp_mapping_from_gpr_rules(gpr_rules)

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
