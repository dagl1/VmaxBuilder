from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, TypedDict, cast

import pandas as pd

# noinspection PyUnresolvedReferences
from pyomo.environ import (
    Binary,
    ConcreteModel,
    Constraint,
    NonNegativeReals,
    Objective,
    Param,
    Set,
    Var,
    minimize,
    value,
)
from pyomo.opt import SolverFactory

from VmaxBuilder.base.classes import (
    BaseImplementationDiagnostics,
    DiagnosticOutputSpec,
    RealImplementation,
)
from VmaxBuilder.base.configs import FullConfig, InputSpec, OutputSpec, Scaffold
from VmaxBuilder.stages.allocation.FairAllocation.config import FairAllocationConfig
from VmaxBuilder.typing_stubs.allocation.FairALlocation.implementation import (
    FairAllocationConfigProtocol,
)
from VmaxBuilder.utils.custom_logging import CustomLogger


@dataclass
class IFPDefinition:
    name: str
    genes: tuple[str, ...]

    # define hasable as name + genes
    def __hash__(self):
        return hash((self.name, self.genes))


class IFPTrimmingOutput(TypedDict):
    IFP: str
    n_genes_before_trimming: int
    trimmable_genes: list[str]
    genes_trimmed_per_sample: dict[str, list[str]]
    percentage_difference_highest_trimmed_lowest_non_trimmable_per_sample: dict[str, float]
    percentage_difference_highest_trimmed_highest_non_trimmable_per_sample: dict[str, float]


class FairAllocationImplementation(RealImplementation[FairAllocationConfigProtocol]):
    STAGE_NAME = "protein"
    IMPL_NAME = "FairAllocation"
    IMPLEMENTATION_CONFIG_CLASS = FairAllocationConfig
    CHILD_IMPLEMENTATIONS = []
    DIAGNOSTICS: list[type[BaseImplementationDiagnostics]] = []
    INPUTS: list[InputSpec] = [
        InputSpec(
            name="IFP_mapping",
            in_scaffold=True,
            data_type=dict,
        ),
        InputSpec(
            name="protein_abundance_df",
            in_scaffold=True,
            data_type=dict,
        ),
        InputSpec(
            name="trimmable_genes",
            in_scaffold=True,
            optional=True,
            data_type=dict,
        ),
        InputSpec(
            name="gene_to_IFP_mapping",
            in_scaffold=True,
            data_type=dict,
        ),
        InputSpec(
            name="reaction_to_IFP_mapping",
            in_scaffold=True,
            data_type=dict,
        ),
    ]
    OUTPUTS: list[OutputSpec] = [
        OutputSpec(
            name="IFP_sample_abundance_df",
            data_type=pd.DataFrame,
            scaffold_location="outputs",
            save_file_name="IFP_abundance_df",
            saver_args={
                "with_index": True,
            },
            extension=".csv",
            validator=None,
        ),
        OutputSpec(
            name="IFPs_per_sample",
            data_type=dict,
            scaffold_location="outputs",
            save_file_name="IFPs_per_sample",
            extension=".json",
            validator=None,
        ),
        OutputSpec(
            name="base_connected_IFPs",
            data_type=dict,
            scaffold_location="artifacts",
            save_file_name="base_connected_IFPs",
            extension=".json",
            validator=None,
        ),
        OutputSpec(
            name="trimming_output",
            data_type=dict,
            scaffold_location="artifacts",
            save_file_name="trimming_output",
            extension=".json",
            validator=None,
        ),
    ]

    def __init__(self, full_config: FullConfig):
        super().__init__(full_config)
        # Additional initialization if needed

    def create_metadata(self, elapsed_time: float, **kwargs) -> dict[str, Any]:
        metadata = {
            "allocation": {
                "implementation": type(self).__name__,
                "elapsed_time_seconds": elapsed_time,
                "status": "All sample abundance allocated",
                "date_created": pd.Timestamp.now().isoformat(),
                "params": self.get_implementation_config_params(),
            }
        }
        return metadata

    def generate_outputs(self, scaffold: Scaffold):
        protein_abundance_df = cast(
            pd.DataFrame, scaffold.get_scaffold_value("protein_abundance_df")
        )
        IFP_mapping = cast(dict, scaffold.get_scaffold_value("IFP_mapping"))
        trimmable_genes = scaffold.get_scaffold_value("trimmable_genes")
        if trimmable_genes is not None:
            trimmable_genes = cast(set[str], set(trimmable_genes))

        (
            time_elapsed,
            (
                base_connected_IFPs,
                base_connected_component_diagnostics,
                per_sample_IFP_abundances,
                trimming_output,
                IFPs_per_sample,
            ),
        ) = self.get_time_decorator(self.run_IFP_allocation)(
            protein_abundance_df,
            IFP_mapping,
            trimmable_genes,
        )

        metadata = self.create_metadata(
            elapsed_time=time_elapsed,
        )
        base_connected_component_diagnostic = DiagnosticOutputSpec(
            data=base_connected_component_diagnostics,
            save_file_name="connected_component_diagnostics",
            extensions=".json",
            data_type=dict,
        )
        IFP_sample_abundance_df = pd.DataFrame.from_dict(
            per_sample_IFP_abundances,
            orient="index",
        ).transpose()

        new_scaffold_objects = {
            "outputs": {
                "IFP_sample_abundance_df": IFP_sample_abundance_df,
            },
            "artifacts": {
                "trimming_output": trimming_output,
                "IFPs_per_sample": IFPs_per_sample,
            },
            "diagnostics": {"allocation": [base_connected_component_diagnostic]},
            "metadata": metadata,
        }
        return new_scaffold_objects

    def convert_IFP_to_IFPDefinition(
        self,
        IFP_mapping: dict[str, Any],
        allowed_genes: set[str],
    ) -> dict[str, IFPDefinition]:
        IFP_definitions: dict[str, IFPDefinition] = {}
        for _, gpr_data in IFP_mapping.items():
            IFPs = gpr_data.get("IFP_objects")
            if IFPs is None:
                continue
            for IFP in IFPs:
                IFP_name = IFP.get("IFP")
                genes = tuple(IFP.get("genes_in_IFP", []))
                genes = tuple(gene for gene in genes if gene in allowed_genes)
                if IFP_name is not None and genes:
                    IFP_definitions[IFP_name] = IFPDefinition(name=IFP_name, genes=genes)
        return IFP_definitions

    def run_IFP_allocation(
        self,
        protein_abundance_df: pd.DataFrame,
        IFP_mapping: dict[str, Any],
        trimmable_genes: set[str] | None,
    ) -> tuple[
        list[set[str]],
        dict[str, Any],
        dict[str, dict[str, float]],
        dict[str, IFPTrimmingOutput],
        dict[str, list[dict[str, str | list[str] | dict[str, float]]]],
    ]:
        IFPs_per_sample = {}
        (
            _,
            base_connected_IFPs,
            base_non_connected_IFPs,
            base_connected_component_diagnostics,
        ) = self.prepare_IFPs(
            IFP_mapping,
            [],
        )
        IFP_definitions = self.convert_IFP_to_IFPDefinition(
            IFP_mapping, set(protein_abundance_df.index)
        )
        connected_IFP_definitions = {
            IFP_name: IFP_definitions[IFP_name]
            for component in base_connected_IFPs
            for IFP_name in component
            if IFP_name in IFP_definitions
        }
        trimming_output = {}
        IFPs_per_sample = {}
        if (
            hasattr(self.full_config.protein, "trim_enable")
            and self.full_config.protein.trim_enable
        ):
            if trimmable_genes is None:
                raise ValueError("Trimming is enabled, but no trimmable_genes were provided.")
            (IFPs_per_sample, trimming_output) = self.trim_IFPs(
                protein_abundance_df,
                IFP_mapping,
                self.full_config.allocation.trim_minimum_proteins_in_IFP,
                trimmable_genes,
            )

        quadratic_model = self.prepare_quadratic_problem_model(
            list(connected_IFP_definitions.values()), list(protein_abundance_df.index)
        )
        solver_factory = SolverFactory("gurobi")
        # todo: allow different solvers

        per_sample_IFP_abundances: dict[str, dict[str, float]] = {}
        for _sample in protein_abundance_df.columns:
            (
                sample_specific_IFP_mapping,
                sample_specific_connected_IFPs,
                sample_specific_non_connected_IFPs,
                _sample_specific_connected_component_diagnostics,
            ) = self.prepare_IFPs(
                IFP_mapping,
                IFPs_per_sample.get(_sample, []),
            )
            _sample_IFP_abundances = self.resolve_non_connected_IFPs(
                sample_specific_IFP_mapping,
                sample_specific_non_connected_IFPs,
                protein_abundance_df,
                _sample,
            )
            self.adjust_quadratic_model_for_sample_specific(
                quadratic_model,
                [
                    connected_IFP_definitions[IFP_name]
                    for component in sample_specific_connected_IFPs
                    for IFP_name in component
                    if IFP_name in connected_IFP_definitions
                ],
                protein_abundance_df,
                _sample,
            )
            results = solver_factory.solve(quadratic_model, tee=False)
            _sample_IFP_abundances = self.postprocess_results(
                _sample_IFP_abundances,
                quadratic_model,
                solver_result=results,
            )
            per_sample_IFP_abundances[_sample] = _sample_IFP_abundances

        return (
            base_connected_IFPs,
            base_connected_component_diagnostics,
            per_sample_IFP_abundances,
            trimming_output,
            IFPs_per_sample,
        )

    def iteratively_remove_trimmable_proteins(
        self,
        _protein_abundance_df: pd.DataFrame,
        genes: list[str],
        trimmable_genes: set[str],
        trim_minimum_proteins_in_IFP: int,
        IFP_output: IFPTrimmingOutput,
        trimmed_IFPs_per_sample: dict[
            str, list[dict[str, str | list[str] | dict[str, float]]]
        ],
    ) -> None:
        genes = [str(gene) for gene in genes if gene in _protein_abundance_df.index]
        protein_abundance_df = _protein_abundance_df.loc[genes]
        protein_abundance_df = protein_abundance_df.apply(
            pd.to_numeric, errors="coerce"
        ).astype(float)

        for sample in protein_abundance_df.columns:
            trimmed = False
            sample_values = protein_abundance_df[sample].to_numpy(dtype=float)
            protein_abundances: dict[str, float] = dict(
                zip(genes, sample_values, strict=True)
            )
            sorted_genes = sorted(
                protein_abundances,
                key=lambda gene: protein_abundances[gene],
            )
            trimmed_genes_in_sample = []
            while (
                len(sorted_genes) > trim_minimum_proteins_in_IFP
                and sorted_genes[0] in trimmable_genes
            ):
                trimmed_gene = sorted_genes.pop(0)
                trimmed_genes_in_sample.append(trimmed_gene)
                trimmed = True
                IFP_output["genes_trimmed_per_sample"].setdefault(sample, []).append(
                    trimmed_gene
                )

            # calculate the percentage difference between the highest trimmed and
            # lowest non-trimmable protein
            if trimmed:
                per_sample_IFP_mapping = {
                    "IFP": IFP_output["IFP"],
                    "original_genes": genes.copy(),
                    "trimmed_genes_in_IFP": trimmed_genes_in_sample.copy(),
                    "abundance_of_trimmed_genes": {
                        gene: protein_abundances[gene] for gene in trimmed_genes_in_sample
                    },
                    "remaining_genes_in_IFP": sorted_genes,
                    "abundance_of_remaining_genes": {
                        gene: protein_abundances[gene] for gene in sorted_genes
                    },
                    "sample": sample,
                }
                trimmed_IFPs_per_sample.setdefault(sample, []).append(per_sample_IFP_mapping)
                highest_abundance_trimmed_value = protein_abundances[
                    IFP_output["genes_trimmed_per_sample"][sample][-1]
                ]
                lowest_abundance_non_trimmable_value = protein_abundances[sorted_genes[0]]
                highest_abundance_non_trimmable_value = protein_abundances[sorted_genes[-1]]
                smallest_percentage_difference = (
                    (lowest_abundance_non_trimmable_value - highest_abundance_trimmed_value)
                    / lowest_abundance_non_trimmable_value
                ) * 100
                IFP_output[
                    "percentage_difference_highest_trimmed_lowest_non_trimmable_per_sample"
                ][sample] = smallest_percentage_difference
                largest_percentage_difference = (
                    (highest_abundance_non_trimmable_value - highest_abundance_trimmed_value)
                    / highest_abundance_non_trimmable_value
                ) * 100
                IFP_output[
                    "percentage_difference_highest_trimmed_highest_non_trimmable_per_sample"
                ][sample] = largest_percentage_difference

    def trim_IFPs(
        self,
        protein_abundance_df: pd.DataFrame,
        IFP_mapping: dict[str, Any],
        trim_minimum_proteins_in_IFP: int,
        trimmable_genes: set[str],
    ) -> tuple[
        dict[str, list[dict[str, str | list[str] | dict[str, float]]]],
        dict[str, IFPTrimmingOutput],
    ]:
        gpr_rules = list(IFP_mapping.keys())
        trimming_output = {}
        trimmed_IFPs_per_sample: dict[
            str, list[dict[str, str | list[str] | dict[str, float]]]
        ] = {}
        for gpr_rule in gpr_rules:
            IFPs = IFP_mapping[gpr_rule].get("IFP_objects")
            if IFPs is None:
                continue
            for IFP in IFPs:
                genes = IFP.get("genes_in_IFP")

                trimmable_genes_in_IFP = [
                    str(gene) for gene in genes if gene in trimmable_genes
                ]
                IFP_output = IFPTrimmingOutput(
                    IFP=IFP.get("IFP"),
                    n_genes_before_trimming=len(genes),
                    trimmable_genes=trimmable_genes_in_IFP,
                    genes_trimmed_per_sample={},
                    percentage_difference_highest_trimmed_lowest_non_trimmable_per_sample={},
                    percentage_difference_highest_trimmed_highest_non_trimmable_per_sample={},
                )

                if len(genes) < trim_minimum_proteins_in_IFP:
                    continue
                if not any(gene in trimmable_genes for gene in genes):
                    continue

                self.iteratively_remove_trimmable_proteins(
                    protein_abundance_df,
                    genes,
                    trimmable_genes,
                    trim_minimum_proteins_in_IFP,
                    IFP_output,
                    trimmed_IFPs_per_sample,
                )
                IFP_str = IFP.get("IFP")
                trimming_output[IFP_str] = IFP_output

        new_trimmed_IFPs_per_sample = {}
        for sample, IFP_list in trimmed_IFPs_per_sample.items():
            # only keep IFPs that are trimmed in this sample
            new_IFP_list = [
                IFP_data for IFP_data in IFP_list if len(IFP_data["trimmed_genes_in_IFP"]) > 0
            ]
            if new_IFP_list:
                new_trimmed_IFPs_per_sample[sample] = new_IFP_list

        return (trimmed_IFPs_per_sample, trimming_output)

    def adjust_sample_specific_IFP_mapping(
        self,
        IFP_mapping: dict[str, Any],
        sample_specific_IFPs: list[dict[str, str | list[str] | dict[str, float]]],
    ) -> dict[str, Any]:
        # we check any IFPs in the trimmed_IFPs_per_sample,
        # if any are trimmed, we adjust our IFP mapping to reflect these trimmed IFPs,
        # if we have duplicate IFPs, we only keep 1
        adjusted_IFP_mapping = deepcopy(IFP_mapping)
        if not sample_specific_IFPs:
            return adjusted_IFP_mapping

        self._adjust_IFP_mapping(sample_specific_IFPs, adjusted_IFP_mapping)
        # we remove any duplicate IFPs that may have been created by trimming,
        # keeping only the first occurrence
        self._remove_duplicate_IFPs(adjusted_IFP_mapping)

        # ensure that if we have trimmed genes, that there are differences between
        # the IFP_mapping and the adjusted_IFP_mapping

        if self._compare_IFP_mappings(IFP_mapping, adjusted_IFP_mapping):
            self.logger.valid("Adjusted IFP mapping differs from original IFP mapping.")
        else:
            self.logger.warning(
                "Adjusted IFP mapping does not differ from original IFP mapping. "
                "This may indicate that no trimming occurred or "
                "that the trimming did not affect the IFPs."
            )

        return adjusted_IFP_mapping

    def _adjust_IFP_mapping(
        self,
        sample_specific_IFPs: list[dict[str, str | list[str] | dict[str, float]]],
        adjusted_IFP_mapping: dict[str, Any],
    ):
        for IFP_data in sample_specific_IFPs:
            sample_IFP = IFP_data.get("IFP")
            # find the corresponding IFP in the adjusted_IFP_mapping
            for gpr_rule, gpr_data in adjusted_IFP_mapping.items():
                IFPs = gpr_data.get("IFP_objects")
                if IFPs is None:
                    continue
                for i, IFP in enumerate(IFPs):
                    if IFP.get("IFP") == sample_IFP:
                        # update the genes_in_IFP to the trimmed version
                        adjusted_IFP_mapping[gpr_rule]["IFP_objects"][i]["genes_in_IFP"] = (
                            IFP_data["remaining_genes_in_IFP"]
                        )

    def _remove_duplicate_IFPs(
        self,
        adjusted_IFP_mapping: dict[str, Any],
    ):
        seen_IFPs = set()
        for gpr_rule, gpr_data in adjusted_IFP_mapping.items():
            IFPs = gpr_data.get("IFP_objects")
            if IFPs is None:
                continue
            unique_IFPs = []
            for IFP in IFPs:
                IFP_str = IFP.get("IFP")
                if IFP_str not in seen_IFPs:
                    seen_IFPs.add(IFP_str)
                    unique_IFPs.append(IFP)
            adjusted_IFP_mapping[gpr_rule]["IFP_objects"] = unique_IFPs

    def _compare_IFP_mappings(
        self,
        original_IFP_mapping: dict[str, Any],
        adjusted_IFP_mapping: dict[str, Any],
    ) -> bool:
        # Compare the original and adjusted IFP mappings to check for differences
        for gpr_rule, original_gpr_data in original_IFP_mapping.items():
            adjusted_gpr_data = adjusted_IFP_mapping.get(gpr_rule)
            if adjusted_gpr_data is None:
                return True  # GPR rule missing in adjusted mapping

            original_IFPs = original_gpr_data.get("IFP_objects", [])
            adjusted_IFPs = adjusted_gpr_data.get("IFP_objects", [])

            if len(original_IFPs) != len(adjusted_IFPs):
                return True  # Different number of IFPs

            for original_IFP, adjusted_IFP in zip(original_IFPs, adjusted_IFPs, strict=False):
                if original_IFP.get("genes_in_IFP") != adjusted_IFP.get("genes_in_IFP"):
                    return True  # Different genes in IFP

        return False  # No differences found

    def _IFP_to_genes_mapping(
        self,
        IFP_mapping: dict[str, Any],
    ) -> dict[str, set[str]]:
        IFP_to_genes: dict[str, set[str]] = {}
        for _, IFP_data in IFP_mapping.items():
            IFPs = IFP_data.get("IFP_objects")

            if IFPs is None:
                continue

            for IFP in IFPs:
                IFP_name = IFP.get("IFP")
                genes = set(IFP.get("genes_in_IFP", []))

                if IFP_name is None:
                    continue

                IFP_to_genes[IFP_name] = genes

        return IFP_to_genes

    @staticmethod
    def dfs(
        node: str, component: set[str], visited: set[str], graph: dict[str, set[str]]
    ) -> None:
        visited.add(node)
        component.add(node)

        for neighbor in graph[node]:
            if neighbor not in visited:
                FairAllocationImplementation.dfs(neighbor, component, visited, graph)

    def get_connected_components(
        self,
        IFP_mapping: dict[str, Any],
    ) -> tuple[list[set[str]], list[str], dict[str, Any]]:
        IFP_to_genes = self._IFP_to_genes_mapping(IFP_mapping)

        graph: dict[str, set[str]] = {IFP_name: set() for IFP_name in IFP_to_genes}
        IFP_names = list(IFP_to_genes)
        for i, IFP_a in enumerate(IFP_names):
            genes_a = IFP_to_genes[IFP_a]

            for IFP_b in IFP_names[i + 1 :]:
                genes_b = IFP_to_genes[IFP_b]

                # IFPs are connected if they share a gene
                if genes_a & genes_b:
                    graph[IFP_a].add(IFP_b)
                    graph[IFP_b].add(IFP_a)

        visited: set[str] = set()
        connected_components: list[set[str]] = []

        for node in graph:
            if node not in visited:
                component: set[str] = set()
                self.dfs(node, component, visited, graph)
                connected_components.append(component)

        non_connected_IFPs = [
            next(iter(component)) for component in connected_components if len(component) == 1
        ]
        connected_components = [
            component for component in connected_components if len(component) > 1
        ]
        connected_genes: list[set[str]] = []
        non_connected_genes: set[str] = set()

        for component in connected_components:
            component_genes: set[str] = set()
            for IFP in component:
                component_genes.update(IFP_to_genes[IFP])
            if len(component) > 1:
                connected_genes.append(component_genes)
            else:
                non_connected_genes.update(component_genes)

        self.validate_connected_components(
            connected_genes, connected_components, non_connected_genes, IFP_to_genes
        )
        diagnostics_payload = {
            "connected_IFP_components": len(connected_genes),
            "non_connected_IFPs": len(non_connected_IFPs),
            "genes_in_connected_components": sum(len(genes) for genes in connected_genes),
            "genes_in_non_connected_components": len(non_connected_genes),
            "total_unique_genes_in_IFP_mapping": len(
                set().union(*IFP_to_genes.values()) if IFP_to_genes else set()
            ),
            "genes_accounted_for": sum(len(genes) for genes in connected_genes)
            + len(non_connected_genes),
        }

        return connected_components, non_connected_IFPs, diagnostics_payload

    def validate_connected_components(
        self,
        connected_genes: list[set[str]],
        connected_components: list[set[str]],
        non_connected_genes: set[str],
        IFP_to_genes: dict[str, set[str]],
    ) -> None:
        # ensure that any gene in non_connected_genes is not in any of the connected_genes
        if non_connected_genes & set().union(*connected_genes):
            raise ValueError(
                "Some genes are present in both connected and non-connected components."
            )
        # ensure that any gene in a connected IFPs is not in any of the non_connected_genes
        if any(
            IFP_to_genes[IFP] & non_connected_genes
            for component in connected_components
            for IFP in component
        ):
            raise ValueError(
                "Some genes in connected IFPs are present in non-connected components."
            )

    def validate_quadratic_model_result_without_trimming(
        self,
    ):
        pass

    def validate_quadratic_model_result_with_trimming(
        self,
    ):
        pass

    def prepare_IFPs(
        self,
        IFP_mapping: dict[str, Any],
        sample_specific: list[dict[str, str | list[str] | dict[str, float]]],
    ) -> tuple[dict[str, Any], list[set[str]], list[str], dict[str, Any]]:
        # we check any IFPs in the trimmed_IFPs_per_sample,
        # if any are trimmed, we adjust our IFP mapping to reflect these trimmed IFPs,
        # if we have duplicate IFPs, we only keep 1
        sample_specific_IFP_mapping = self.adjust_sample_specific_IFP_mapping(
            IFP_mapping, sample_specific
        )

        # then we find clumps of connected components, meaning any IFP connected to any other
        # IFP through genes. We do this because the QP only has to consider IFPs that
        # are connected to each other through genes, and we can solve independently.
        # we might not do this, but we can ignore all other gens
        connected_IFPs, non_connected_IFPs, connected_component_diagnostics = (
            self.get_connected_components(sample_specific_IFP_mapping)
        )
        return (
            sample_specific_IFP_mapping,
            connected_IFPs,
            non_connected_IFPs,
            connected_component_diagnostics,
        )

    def resolve_non_connected_IFPs(
        self,
        sample_specific_IFP_mapping: dict[str, Any],
        non_connected_IFPs: list[str],
        protein_abundance_df: pd.DataFrame,
        sample: str,
    ) -> dict[str, Any]:
        # for any IFP that is not connected to any other IFP through genes, we can
        # resolve it immediately
        # if it has only 1 gene, we assign the abundance of that gene to the IFP
        # if it has multiple genes, we assign the minimum abundance of the genes in
        # that IFP to the IFP

        sample_IFP_abundances = {}

        for _, IFP_data in sample_specific_IFP_mapping.items():
            IFPs = IFP_data.get("IFP_objects")
            if IFPs is None:
                continue
            for IFP in IFPs:
                if IFP.get("IFP") in non_connected_IFPs:
                    genes = IFP.get("genes_in_IFP", [])
                    genes = [
                        str(gene) for gene in genes if gene in protein_abundance_df.index
                    ]
                    if len(genes) == 1:
                        sample_IFP_abundances[IFP.get("IFP")] = protein_abundance_df.loc[
                            genes[0], sample
                        ]
                    elif len(genes) > 1:
                        sample_IFP_abundances[IFP.get("IFP")] = protein_abundance_df.loc[
                            genes, sample
                        ].min()

        return sample_IFP_abundances

    #
    def prepare_quadratic_problem_model(
        self,
        connected_IFPs: list[IFPDefinition],
        all_genes: list[str],
    ) -> ConcreteModel:
        genes = sorted({gene for IFP in connected_IFPs for gene in IFP.genes})
        genes = [gene for gene in genes if gene in all_genes]
        IFP_to_genes = {IFP.name: set(IFP.genes) for IFP in connected_IFPs}

        # Gene -> IFPs
        gene_to_IFPs: dict[str, list[str]] = {gene: [] for gene in genes}

        for IFP in connected_IFPs:
            for gene in IFP.genes:
                gene_to_IFPs[gene].append(IFP.name)

        model = ConcreteModel()
        model.IFPs = Set(
            initialize=[IFP.name for IFP in connected_IFPs],
        )
        model.genes = Set(initialize=genes)
        model.gene_IFP_pairs = Set(
            initialize=[(gene, IFP) for IFP in connected_IFPs for gene in IFP.genes],
            dimen=2,
        )

        # Store these on the model so they can be reused later
        model.IFP_to_genes = IFP_to_genes
        model.gene_to_IFPs = gene_to_IFPs

        # Variables
        model.x = Var(
            model.IFPs,
            domain=NonNegativeReals,
        )

        model.deviation_from_max_per_IFP = Var(
            model.IFPs,
            domain=NonNegativeReals,
        )

        # Param
        model.availability = Param(
            model.genes,
            initialize=0.0,
            mutable=True,
            within=NonNegativeReals,
        )
        model.gene_IFP_active = Param(
            model.gene_IFP_pairs,
            initialize=1,
            mutable=True,
            within=Binary,
        )

        model.max_per_IFP = Param(
            model.IFPs,
            initialize=0.0,
            mutable=True,
            within=NonNegativeReals,
        )

        def gene_cannot_exceed_IFPs(model, gene):
            return model.availability[gene] >= sum(
                model.gene_IFP_active[gene, IFP] * model.x[IFP]
                for IFP in model.IFPs
                if (gene, IFP) in model.gene_IFP_pairs
            )

        def determining_percentage_rule(model, IFP):
            max_value = model.max_per_IFP[IFP]

            return model.deviation_from_max_per_IFP[IFP] == (1 - model.x[IFP] / max_value)

        model.gene_cannot_exceed_IFPs_constraints = Constraint(
            model.genes,
            rule=gene_cannot_exceed_IFPs,
        )
        model.per_IFP_percentage_of_max_constraints = Constraint(
            model.IFPs,
            rule=determining_percentage_rule,
        )
        model.obj = Objective(
            expr=sum(
                model.deviation_from_max_per_IFP[IFP] ** 2  # ty: ignore
                for IFP in model.IFPs
            ),
            sense=minimize,
        )

        return model

    def adjust_quadratic_model_for_sample_specific(
        self,
        quadratic_model: ConcreteModel,
        sample_specific_IFPs: list[IFPDefinition],
        protein_abundance_df: pd.DataFrame,
        sample: str,
    ) -> None:
        for gene in quadratic_model.genes:  # ty: ignore
            value = protein_abundance_df.at[gene, sample]

            if pd.isna(value):
                raise ValueError(f"Missing abundance for gene '{gene}' in sample '{sample}'.")

            quadratic_model.availability[gene] = float(value)  # ty: ignore

        for gene, IFP in quadratic_model.gene_IFP_pairs:  # ty: ignore
            quadratic_model.gene_IFP_active[gene, IFP] = 1  # ty: ignore

        sample_specific_genes = {IFP.name: set(IFP.genes) for IFP in sample_specific_IFPs}

        for IFP in quadratic_model.IFPs:  # ty: ignore
            genes = sample_specific_genes.get(
                IFP,
                quadratic_model.IFP_to_genes[IFP],  # ty: ignore
            )

            original_genes = quadratic_model.IFP_to_genes[IFP]  # ty: ignore

            for gene in original_genes:
                if gene not in genes:
                    quadratic_model.gene_IFP_active[gene, IFP] = 0  # ty: ignore

            if not genes:
                raise ValueError(
                    f"IFP '{IFP}' has no genes remaining after trimming "
                    f"for sample '{sample}'."
                )

            quadratic_model.max_per_IFP[IFP] = min(  # ty:ignore
                float(quadratic_model.availability[gene].value)  # ty: ignore
                for gene in genes
            )

    def postprocess_results(
        self,
        sample_IFP_abundances: dict[str, float],
        quadratic_model: ConcreteModel,
        solver_result,
    ):
        # Check solver status
        if solver_result.solver.termination_condition != "optimal":
            raise ValueError(
                "Solver did not find an optimal solution. "
                f"Termination condition: "
                f"{solver_result.solver.termination_condition}"
            )

        if solver_result.solver.status != "ok":
            raise ValueError(
                f"Solver did not complete successfully. Status: {solver_result.solver.status}"
            )

        # Extract the optimized abundance for each IFP that is present
        # in sample_IFP_abundances.
        per_IFP_abundances = {
            IFP: float(value(quadratic_model.x[IFP]))  # ty: ignore
            for IFP in sample_IFP_abundances
            if IFP in quadratic_model.IFPs  # ty: ignore
        }

        # Replace the original/sample-specific values with the QP allocation.
        sample_IFP_abundances.update(per_IFP_abundances)

        return sample_IFP_abundances


if __name__ == "__main__":
    import json
    from pathlib import Path

    base_dir = r"/home/p70088775/git/VmaxBuilder/data/run_example_output/DCM_magnet_run/"

    protein_abundance_path = Path(base_dir) / "outputs" / "protein_abundance_df.csv"
    protein_abundance_df = pd.read_csv(
        protein_abundance_path,
        index_col=0,
    )
    IFP_mapping_path = Path(base_dir) / "outputs" / "IFP_mapping.json"
    with open(IFP_mapping_path, "r") as f:
        IFP_mapping = json.load(f)

    trimmable_genes_path = Path(base_dir) / "outputs" / "trimmable_genes.json"
    with open(trimmable_genes_path, "r") as f:
        trimmable_genes = set(json.load(f))

    allocator = object.__new__(FairAllocationImplementation)
    allocator.logger = CustomLogger(
        "FairAllocationImplementation",
    )

    (
        _,
        base_connected_IFPs,
        base_non_connected_IFPs,
        base_connected_component_diagnostics,
    ) = allocator.prepare_IFPs(
        IFP_mapping,
        [],
    )
    print(
        f"Base connected IFPs: len={len(base_connected_IFPs)}",
    )
    print(
        f"Base non-connected IFPs: len={len(base_non_connected_IFPs)}",
    )

    IFP_definitions = allocator.convert_IFP_to_IFPDefinition(
        IFP_mapping, set(protein_abundance_df.index)
    )
    connected_IFP_definitions = {
        IFP_name: IFP_definitions[IFP_name]
        for component in base_connected_IFPs
        for IFP_name in component
        if IFP_name in IFP_definitions
    }
    IFPs_per_sample = {}
    (IFPs_per_sample, trimming_output) = allocator.trim_IFPs(
        protein_abundance_df,
        IFP_mapping,
        7,
        trimmable_genes,
    )

    solver_factory = SolverFactory("gurobi")
    quadratic_model = allocator.prepare_quadratic_problem_model(
        list(connected_IFP_definitions.values()), list(protein_abundance_df.index)
    )

    for _sample in protein_abundance_df.columns:
        (
            sample_specific_IFP_mapping,
            sample_specific_connected_IFPs,
            sample_specific_non_connected_IFPs,
            _sample_specific_connected_component_diagnostics,
        ) = allocator.prepare_IFPs(
            IFP_mapping,
            IFPs_per_sample.get(_sample, []),
        )
        sample_IFP_abundances = allocator.resolve_non_connected_IFPs(
            sample_specific_IFP_mapping,
            sample_specific_non_connected_IFPs,
            protein_abundance_df,
            _sample,
        )
        ten_IFPs = list(sample_IFP_abundances.items())[:10]
        print(
            f"Sample: {_sample}, First 10 IFP Abundances: {ten_IFPs}, "
            f"values: {list(sample_IFP_abundances.values())[:10]}"
        )
        allocator.adjust_quadratic_model_for_sample_specific(
            quadratic_model,
            [
                connected_IFP_definitions[IFP_name]
                for component in sample_specific_connected_IFPs
                for IFP_name in component
                if IFP_name in connected_IFP_definitions
            ],
            protein_abundance_df,
            _sample,
        )
        results = solver_factory.solve(quadratic_model, tee=False)
        sample_IFP_abundances = allocator.postprocess_results(
            sample_IFP_abundances, quadratic_model, solver_result=results
        )
        last_ten_IFPs = list(sample_IFP_abundances.items())[-10:]
        print(
            f"Sample: {_sample}, Last 10 IFP Abundances: {last_ten_IFPs}, "
            f"values: {list(sample_IFP_abundances.values())[-10:]}"
        )
