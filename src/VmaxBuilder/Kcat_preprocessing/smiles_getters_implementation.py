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
    STAGE_NAME: str = "Kcat"
    IMPL_NAME: str = "SMILES_transcript_getter"
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
