from cobra.core.model import Model
from pandas import DataFrame

from VmaxBuilder.base.classes import BaseImplementation
from VmaxBuilder.base.configs import InputSpec, OutputSpec
from VmaxBuilder.base.registry import register_implementation
from VmaxBuilder.stages.model.default.config import ModelConfig
from VmaxBuilder.stages.model.default.diagnostics import ModelDiagnostics
from VmaxBuilder.utils.file_handling import load_existing_file_based_on_extension


@register_implementation("model", "default")
class DefaultIrreversibleModelImplementation(BaseImplementation):
    STAGE_NAME = "model"
    IMPL_NAME = "dummy_cobra"
    INPUTS: list[InputSpec] = [
        InputSpec(
            name="cobra_model",
            data_type=Model,
            scaffold_key="cobra_model",
            loader=load_existing_file_based_on_extension,
            loader_args={"is_cobra_model": True},
            file_key="model_",
            extensions=(
                ".json",
                ".xml",
                ".yml",
                ".yaml",
                ".mat",
            ),
        ),
        InputSpec(
            name="transcript_df",
            data_type=DataFrame,
            scaffold_key="transcript_df",
            optional=True,
            loader=load_existing_file_based_on_extension,
            file_key="transcript_df",
            extensions=(
                ".json",
                ".csv",
                ".tsv",
            ),
        ),
        InputSpec(
            name="smiles_df",
            data_type=DataFrame,
            scaffold_key="smiles_df",
            optional=True,
            loader=load_existing_file_based_on_extension,
            file_key="smiles_df",
            extensions=(
                ".json",
                ".csv",
                ".tsv",
            ),
        ),
    ]
    OUTPUTS: list[OutputSpec] = []
    CONFIG_CLASS = ModelConfig
    diagnostics = ModelDiagnostics()
