from cobra.core.model import Model
from pandas import DataFrame

from VmaxBuilder.base.classes import BaseImplementation
from VmaxBuilder.base.configs import FullConfig, InputSpec, OutputSpec
from VmaxBuilder.stages.protein.expression.config import ExpressionConfig
from VmaxBuilder.stages.protein.protein import ProteinStageConfig
from VmaxBuilder.typing_stubs.protein.expression.implementation import (
    ExpressionConfigProtocol,
)


class DefaultExpressionImplementation(BaseImplementation[ExpressionConfigProtocol]):
    BASE_STAGE_CONFIG = ProteinStageConfig
    IMPLEMENTATION_CONFIG_CLASS = ExpressionConfig
    _RESOLVED_CONFIG_CLASS = ExpressionConfigProtocol
    STAGE_NAME = "protein"
    IMPL_NAME = "expression_only"
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
        ),
        InputSpec(
            name="expression_df",
            data_type=DataFrame,
            prefix="data__",
            extensions=(
                ".json",
                ".csv",
                ".tsv",
            ),
        ),
    ]
    OUTPUTS: list[OutputSpec] = [
        OutputSpec(
            "processed_expression_df",
            data_type=DataFrame,
            scaffold_location="outputs",
            save_file_name="processed_expression_df",
            extension=".feather",
            validator=None,
        ),
    ]
    DIAGNOSTICS = []

    def __init__(self, full_config: FullConfig):
        super().__init__(full_config)

    def generate_outputs(self, scaffold):
        # This
        return {}
