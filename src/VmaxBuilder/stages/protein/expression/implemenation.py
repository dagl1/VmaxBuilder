from pandas import DataFrame

from VmaxBuilder.base.classes import BaseImplementation
from VmaxBuilder.base.configs import InputSpec, OutputSpec
from VmaxBuilder.base.registry import register_implementation
from VmaxBuilder.utils.file_handling import load_existing_file_based_on_extension


@register_implementation("protein", "default_expression_only")
class DefaultExpressionImplementation(BaseImplementation):
    STAGE_NAME = "protein"
    IMPL_NAME = "expression_only"
    CHILD_IMPLEMENTATIONS = []
    INPUTS: list[InputSpec] = [
        InputSpec(
            name="cobra_model",
            data_type=DataFrame,
            scaffold_key="cobra_model",
        ),
        InputSpec(
            name="transcript_df",
            data_type=DataFrame,
            scaffold_key="transcript_df",
        ),
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
    ]
    OUTPUTS: list[OutputSpec] = []
    DIAGNOSTICS = []
