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
            name="reaction_to_ifps",
            in_scaffold=True,
            data_type=dict,
        ),
        InputSpec(
            name="IFP_to_reactions",
            in_scaffold=True,
            data_type=dict,
        ),
    ]
    OUTPUTS: list[OutputSpec] = [
        #     OutputSpec(
        #         name="imputed_PTR_df",
        #         data_type=DataFrame,
        #         scaffold_location="outputs",
        #         save_file_name="imputed_PTR_df",
        #         saver_args={
        #             "with_index": True,
        #         },
        #         extension=".csv",
        #         validator=None,
        #     ),
    ]

    def __init__(self, full_config: FullConfig):
        super().__init__(full_config)
        # Additional initialization if needed

    def generate_outputs(self, scaffold: Scaffold):
        _protein_abundance_df = cast(
            pd.DataFrame, scaffold.get_scaffold_value("protein_abundance_df")
        )
        _ifp_mapping = cast(dict, scaffold.get_scaffold_value("ifp_mapping"))
        _reaction_to_ifps = cast(dict, scaffold.get_scaffold_value("reaction_to_ifps"))
        _ifp_to_reactions = cast(dict, scaffold.get_scaffold_value("ifp_to_reactions"))
        return {}
