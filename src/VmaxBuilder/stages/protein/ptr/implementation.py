from pandas import DataFrame

from VmaxBuilder.base.classes import BaseImplementation
from VmaxBuilder.base.configs import FullConfig, InputSpec, OutputSpec
from VmaxBuilder.utils.file_handling import load_existing_file_based_on_extension


class SimplePTRImputationImplementation(BaseImplementation):
    STAGE_NAME = "protein"
    IMPL_NAME = "simple_ptr_imputation"
    CHILD_IMPLEMENTATIONS = []
    INPUTS: list[InputSpec] = [
        InputSpec(
            name="PTR_df",
            data_type=DataFrame,
            prefix="PTR__",
            extensions=(
                ".json",
                ".csv",
                ".tsv",
            ),
        ),
        InputSpec(
            name="transcript_df",
            data_type=DataFrame,
            loader=None,
            optional=True,
        ),
    ]

    def __init__(self, full_config: FullConfig):
        super().__init__(full_config)
        # Additional initialization if needed

    def generate_outputs(self, scaffold):
        # This
        return {}
