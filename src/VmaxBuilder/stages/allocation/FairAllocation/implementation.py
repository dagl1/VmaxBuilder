from __future__ import annotations

from typing import Any, cast

import pandas as pd

from VmaxBuilder.base.classes import BaseImplementationDiagnostics, RealImplementation
from VmaxBuilder.base.configs import FullConfig, InputSpec, OutputSpec, Scaffold
from VmaxBuilder.stages.allocation.FairAllocation.config import FairAllocationConfig
from VmaxBuilder.typing_stubs.allocation.FairALlocation.implementation import (
    FairAllocationConfigProtocol,
)


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
            name="trimmed_genes_per_IFP_per_sample",
            data_type=dict,
            scaffold_location="outputs",
            save_file_name="trimmed_genes_per_IFP_per_sample",
            extension=".json",
            validator=None,
        ),
    ]

    def __init__(self, full_config: FullConfig):
        super().__init__(full_config)
        # Additional initialization if needed

    def generate_outputs(self, scaffold: Scaffold):
        _protein_abundance_df = cast(
            pd.DataFrame, scaffold.get_scaffold_value("protein_abundance_df")
        )
        _IFP_mapping = cast(dict, scaffold.get_scaffold_value("IFP_mapping"))
        _gene_to_IFPs = cast(dict, scaffold.get_scaffold_value("gene_to_IFP_mapping"))
        _reaction_to_IFPs = cast(dict, scaffold.get_scaffold_value("reaction_to_IFP_mapping"))

        return {}

    def run_IFP_allocation(
        self,
        _protein_abundance_df: pd.DataFrame,
        _IFP_mapping: dict[str, Any],
        _gene_to_IFPs: dict[str, Any],
        _reaction_to_IFPs: dict[str, Any],
    ) -> tuple[pd.DataFrame, dict[str, Any]]:

        if self.config.protein.trim_enable:
            _IFP_mapping = self.prepare_IFPs(_IFP_mapping)

        for sample in _protein_abundance_df.columns:
            quadratic_model = self.prepare_quadratic_model(
                _protein_abundance_df, _IFP_mapping
            )
            result = self.run_quadratic_model(quadratic_model)
            postprocessed_result = self.postprocess_results(result)

    def prepare_IFPs(
        self,
        _IFP_mapping: dict[str, Any],
    ) -> dict[str, Any]:
        pass

    def prepare_quadratic_model(
        self,
    ):
        pass

    def run_quadratic_model(
        self,
    ):
        pass

    def postprocess_results(
        self,
    ):
        pass
