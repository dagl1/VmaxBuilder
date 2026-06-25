from queue import Full
from typing import TYPE_CHECKING

from cobra.core.model import Model
from pandas import DataFrame

from VmaxBuilder.base.classes import BaseImplementation
from VmaxBuilder.base.configs import FullConfig, InputSpec, OutputSpec
from VmaxBuilder.base.registry import register_implementation
from VmaxBuilder.stages.model.default.config import ModelConfig
from VmaxBuilder.stages.model.default.diagnostics import ModelDiagnostics
from VmaxBuilder.typing_stubs.model.default.implementation import DefaultConfig
from VmaxBuilder.utils.file_handling import load_existing_file_based_on_extension

if TYPE_CHECKING:
    pass


@register_implementation("model", "default")
class DefaultIrreversibleModelImplementation(BaseImplementation):
    STAGE_NAME = "model"
    IMPL_NAME = "dummy_cobra"
    INPUTS: list[InputSpec] = [
        InputSpec(
            name="cobra_model",
            data_type=Model,
            loader_args={
                "is_cobra_model": True,
                # "load_cobra_fast": True,
            },
            prefix="model_",
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
            optional=True,
            prefix="transcript_df",
            extensions=(
                ".json",
                ".csv",
                ".tsv",
            ),
        ),
        InputSpec(
            name="smiles_df",
            data_type=DataFrame,
            optional=True,
            prefix="smiles_df",
            extensions=(
                ".json",
                ".csv",
                ".tsv",
            ),
        ),
    ]
    OUTPUTS: list[OutputSpec] = []
    CONFIG_CLASS = ModelConfig
    DIAGNOSTICS = ModelDiagnostics()
    _RESOLVED_CONFIG_CLASS = DefaultConfig

    def __init__(self, full_config: FullConfig):
        super().__init__(full_config)
        # Additional initialization if needed

    def generate_outputs(self, scaffold):
        # This
        return {}
