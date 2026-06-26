from pandas import DataFrame

from VmaxBuilder.base.classes import BaseImplementation
from VmaxBuilder.base.configs import FullConfig, InputSpec, OutputSpec
from VmaxBuilder.utils.file_handling import load_existing_file_based_on_extension


class DefaultExpressionImplementation(BaseImplementation):
    STAGE_NAME = "protein"
    IMPL_NAME = "expression_only"
    CHILD_IMPLEMENTATIONS = []
    INPUTS: list[InputSpec] = [
        InputSpec(
            name="cobra_model",
            data_type=DataFrame,
            loader=None,
        ),
        InputSpec(
            name="transcript_df",
            data_type=DataFrame,
            loader=None,
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
    OUTPUTS: list[OutputSpec] = []
    DIAGNOSTICS = []

    def __init__(self, full_config: FullConfig):
        super().__init__(full_config)
        # Additional initialization if needed

    def generate_outputs(self, scaffold):
        # This
        return {}
