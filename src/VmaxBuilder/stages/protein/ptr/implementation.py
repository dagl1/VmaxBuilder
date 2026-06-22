from pandas import DataFrame

from VmaxBuilder.base.classes import BaseImplementation
from VmaxBuilder.base.configs import InputSpec, OutputSpec
from VmaxBuilder.base.registry import register_implementation
from VmaxBuilder.utils.file_handling import load_existing_file_based_on_extension


class SimplePTRImputationImplementation(BaseImplementation):
    STAGE_NAME = "protein"
    IMPL_NAME = "simple_ptr_imputation"
    CHILD_IMPLEMENTATIONS = []
    INPUTS: list[InputSpec] = [
        InputSpec(
            name="expression_df",
            data_type=DataFrame,
            scaffold_key="expression_df",
            loader=load_existing_file_based_on_extension,
            file_key="expression_df",
            extensions=(
                ".json",
                ".csv",
                ".tsv",
            ),
        ),
        InputSpec(
            name="transcript_df",
            data_type=DataFrame,
            scaffold_key="transcript_df",
            optional=True,
        ),
    ]
