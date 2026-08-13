from __future__ import annotations

from typing import Any, cast

import pandas as pd

from VmaxBuilder.base.classes import BaseImplementation, RealImplementation
from VmaxBuilder.base.configs import InputSpec, OutputSpec, Scaffold
from VmaxBuilder.stages.protein.protein import ProteinStageConfig
from VmaxBuilder.stages.protein.ptr.config import PTRInputConfig
from VmaxBuilder.stages.protein.ptr.ptr_utils import _normalize_sample_label, is_valid_int
from VmaxBuilder.typing_stubs.protein.ptr.implementation import (
    PTRInputConfigProtocol,
)


class SimplePTRMultiplicationImplementation(RealImplementation[PTRInputConfigProtocol]):
    BASE_STAGE_CONFIG = ProteinStageConfig
    STAGE_NAME = "protein"
    IMPL_NAME = "simple_ptr_multiplication"

    IMPLEMENTATION_CONFIG_CLASS = PTRInputConfig
    CHILD_IMPLEMENTATIONS: list[type[BaseImplementation]] = []

    INPUTS: list[InputSpec] = [
        InputSpec(
            name="processed_expression_df",
            data_type=pd.DataFrame,
            in_scaffold=True,
        ),
        InputSpec(
            name="imputed_PTR_df",
            data_type=pd.DataFrame,
            in_scaffold=True,
        ),
        InputSpec(
            name="sample_type_map",
            data_type=(dict, pd.DataFrame, str),
            optional=True,
            prefix="expression_sample_type_mapping",
            extensions=(
                ".json",
                ".csv",
                ".tsv",
            ),
        ),
    ]
    OUTPUTS: list[OutputSpec] = [
        OutputSpec(
            name="protein_abundance_df",
            data_type=pd.DataFrame,
            scaffold_location="outputs",
            save_file_name="protein_abundance_df",
            saver_args={
                "with_index": True,
            },
            extension=".csv",
            validator=None,
        ),
    ]
    DIAGNOSTICS = []

    def __init__(self, full_config: Any):
        super().__init__(full_config)

    def generate_outputs(self, scaffold: Scaffold) -> dict[str, Any]:
        processed_expression_df = cast(
            pd.DataFrame, scaffold.get_scaffold_value("processed_expression_df")
        )
        imputed_ptr_df = cast(pd.DataFrame, scaffold.get_scaffold_value("imputed_PTR_df"))
        sample_type_map = scaffold.get_scaffold_value("sample_type_map")
        config_sample_type_map = self.full_config.protein.expression_sample_type_map

        expression_validated_sample_type_map = self._validate_sample_type_map_expression_side(
            expression_df=processed_expression_df,
            config_sample_type_map=config_sample_type_map,
            sample_type_map=sample_type_map,
        )
        ptr_validated_sample_type_map = self._validate_sample_type_map_PTR_side(
            ptr_df=imputed_ptr_df,
            validated_sample_type_map=expression_validated_sample_type_map,
        )

        elapsed_time, protein_abundance_df = self.get_time_decorator(
            self.combine_expression_with_ptr
        )(
            expression_df=processed_expression_df,
            ptr_df=imputed_ptr_df,
            sample_type_map=ptr_validated_sample_type_map,
        )
        metadata = self.create_metadata(elapsed_time=elapsed_time)
        # todo: add base diagnostics
        new_scaffold_objects = {
            "outputs": {
                "protein_abundance_df": protein_abundance_df,
            },
            "diagnostics": {},
            "metadata": metadata,
            "artifacts": {},
        }

        return new_scaffold_objects

    def _validate_sample_type_map_PTR_side(
        self,
        ptr_df: pd.DataFrame,
        validated_sample_type_map: dict[str, str],
    ) -> dict[str, str]:
        # ensure that the validated sample type map has values that are in the ptr_df columns
        (
            resolved_sample_type_map,
            validated_sample_type_map,
        ) = self.resolve_sample_type_map(ptr_df, validated_sample_type_map)
        if not all(value in ptr_df.columns for value in resolved_sample_type_map.values()):
            missing_values = [
                value
                for value in resolved_sample_type_map.values()
                if value not in ptr_df.columns
            ]
            possible_values = list(ptr_df.columns)

            raise ValueError(
                f"Validated sample type map has values that are not "
                f"in the PTR dataframe columns: {missing_values}.\n"
                f"Possible values in PTR dataframe columns: {possible_values}."
            )
        return validated_sample_type_map

    def normalize_dataframe_sample_type_map(
        self,
        loaded_sample_type_map: pd.DataFrame,
        expression_df: pd.DataFrame,
    ) -> dict[str, str] | ValueError:
        # if the dataframe has 2 columns,
        # we assume the first is expression and second is ptr
        if loaded_sample_type_map.shape[1] == 2:
            return dict(
                zip(
                    loaded_sample_type_map.iloc[:, 0],
                    loaded_sample_type_map.iloc[:, 1],
                    strict=True,
                )
            )
        # if the dataframe has 1 column, we assume it
        # is in order of the expression columns
        elif loaded_sample_type_map.shape[1] == 1:
            if loaded_sample_type_map.shape[0] != expression_df.shape[1]:
                return ValueError(
                    "Loaded sample type map has a different number of rows "
                    "than the expression dataframe has columns."
                )
            return dict(
                zip(expression_df.columns, loaded_sample_type_map.iloc[:, 0], strict=False)
            )
        else:
            return ValueError(
                "Loaded sample type map dataframe must have either 1 or 2 columns."
            )

    def normalize_dict_sample_type_map(
        self,
        loaded_sample_type_map: dict[str | int, str],
        expression_df: pd.DataFrame,
    ) -> dict[str, str] | ValueError:
        # if the dict has keys that are in the expression columns,
        # we assume it is a mapping
        # it could also be a dict with just keys as indexes
        if all(key in expression_df.columns for key in loaded_sample_type_map.keys()):
            new_loaded_sample_type_map = {
                str(key): value for key, value in loaded_sample_type_map.items()
            }
            return new_loaded_sample_type_map
        # check if some keys match, but not all, then we can raise with indication of
        # which are missing or mistyped
        elif any(key in expression_df.columns for key in loaded_sample_type_map.keys()):
            missing_keys = [
                key
                for key in loaded_sample_type_map.keys()
                if key not in expression_df.columns
            ]
            return ValueError(
                "Loaded sample type map has some keys that are not in the "
                f"expression dataframe columns: {missing_keys}"
            )
        elif all(is_valid_int(key) for key in loaded_sample_type_map.keys()):
            if len(loaded_sample_type_map) < expression_df.shape[1]:
                return ValueError(
                    "Loaded sample type map has a different number of entries than "
                    "the expression dataframe has columns."
                )
            return dict(
                zip(expression_df.columns, loaded_sample_type_map.values(), strict=False)
            )
        else:
            return ValueError(
                "Loaded sample type map dict must have keys that are either "
                "expression column names or integers."
            )

    def normalize_loaded_sample_type_map(
        self,
        loaded_sample_type_map: dict[str | int, str] | pd.DataFrame | None,
        expression_df: pd.DataFrame,
    ) -> dict[str, str] | None | ValueError:
        """
        # we load a csv, tsv, or json
        # this hopefully includes the sample names in the expression (columns)
        # but can also be without sample names and just be in order of the expression columns
        # must at least have the same size, but can be larger
        # we need to normalize this into a dict of expression column name to ptr column name
        # and return this dict
        # if input is None, we haven't loaded any sample type map, so we return None
        """

        if loaded_sample_type_map is None:
            return None

        if isinstance(loaded_sample_type_map, pd.DataFrame):
            return self.normalize_dataframe_sample_type_map(
                loaded_sample_type_map=loaded_sample_type_map,
                expression_df=expression_df,
            )
        elif isinstance(loaded_sample_type_map, dict):
            return self.normalize_dict_sample_type_map(
                loaded_sample_type_map=loaded_sample_type_map,
                expression_df=expression_df,
            )

    def _validate_sample_type_map_expression_side(
        self,
        expression_df: pd.DataFrame,
        config_sample_type_map: dict[str | int, str] | str | None,
        sample_type_map: dict[str | int, str] | None,
    ) -> dict[str, str]:
        if config_sample_type_map is None and sample_type_map is None:
            raise ValueError(
                "No sample type map provided. "
                "Please provide either a config or loaded sample type map."
            )

        def _normalize(map_obj) -> dict[str, str] | None:
            if map_obj is None:
                return None
            if isinstance(map_obj, str):
                return {col: map_obj for col in expression_df.columns}
            res = self.normalize_loaded_sample_type_map(
                loaded_sample_type_map=map_obj,
                expression_df=expression_df,
            )
            return res if isinstance(res, dict) else None

        resolved_config_mapping = _normalize(config_sample_type_map)
        resolved_input_mapping = _normalize(sample_type_map)

        if resolved_config_mapping and resolved_input_mapping:
            self.logger.warning(
                "Both config and loaded sample type maps are provided. "
                "Using config sample type map."
            )
            return resolved_config_mapping

        valid_res = resolved_config_mapping or resolved_input_mapping
        if valid_res:
            return valid_res

        raise ValueError(
            "The provided sample type map(s) are invalid. Please check the input formats."
        )

    def create_metadata(self, elapsed_time: float, **kwargs) -> dict[str, Any]:
        metadata = {
            "PTR_Multiplication": {
                "implementation": type(self).__name__,
                "elapsed_time_seconds": elapsed_time,
                "status": "Expression values multiplied by PTR values",
                "date_created": pd.Timestamp.now().isoformat(),
                "params": self.get_implementation_config_params(),
            }
        }
        return metadata

    def combine_expression_with_ptr(
        self,
        expression_df: pd.DataFrame,
        ptr_df: pd.DataFrame,
        sample_type_map: dict[str, str],
    ) -> pd.DataFrame:
        """Generated: validation needed.

        Description:
            Multiply expression values by PTR values for each gene, using the
            resolved sample-type column mapping to pair expression columns with
            PTR columns.  Genes absent from PTR retain their expression values.

        Args:
            expression_df (pd.DataFrame): Preprocessed expression table
                (genes × expression-samples).
            ptr_df (pd.DataFrame): Preprocessed PTR table
                (genes × tissue-types).
            sample_type_map (dict[str, str] | str | None): Mapping from
                expression column names to PTR column names.  ``str`` maps
                every expression column to the same PTR column; ``None`` falls
                back to direct column intersection.

        Returns:
            pd.DataFrame: Combined protein abundance table with same shape as
            ``expression_df``.
        """
        protein_df = expression_df.copy()
        common_genes = expression_df.index.intersection(ptr_df.index)

        ptr_col_lookup: dict[str, str] = {}
        for ptr_col in ptr_df.columns:
            normalized_ptr_col = _normalize_sample_label(ptr_col)
            ptr_col_lookup.setdefault(normalized_ptr_col, ptr_col)

        if common_genes.empty:
            self.logger.warning(
                "PTR: no overlapping genes between expression and PTR; "
                "returning unmodified expression."
            )
            return protein_df

        for expr_col, ptr_col in sample_type_map.items():
            if expr_col not in expression_df.columns:
                continue
            ptr_col_actual = ptr_col_lookup.get(ptr_col)
            if ptr_col_actual is None:
                self.logger.error(
                    f"PTR: column '{ptr_col}' not found in PTR frame; "
                    f"skipping multiplication for expression column '{expr_col}'."
                )
                continue
            protein_df.loc[common_genes, expr_col] = (
                expression_df.loc[common_genes, expr_col]
                * ptr_df.loc[common_genes, ptr_col_actual]
            )

        return protein_df

    @staticmethod
    def resolve_sample_type_map(
        ptr_df: pd.DataFrame,
        sample_type_map: dict[str, str],
    ) -> tuple[dict[str, str], dict[str, str]]:
        normalized_ptr_col_lookup: dict[str, str] = {}
        for ptr_col in ptr_df.columns:
            normalized_ptr_col = _normalize_sample_label(ptr_col)
            normalized_ptr_col_lookup[normalized_ptr_col] = ptr_col

        resolved_map: dict[str, str] = {}
        for expr_col, ptr_col in sample_type_map.items():
            normalized_target = _normalize_sample_label(ptr_col)

            if normalized_target in normalized_ptr_col_lookup:
                resolved_map[expr_col] = normalized_ptr_col_lookup[normalized_target]
            else:
                resolved_map[expr_col] = ptr_col

        return (resolved_map, sample_type_map)
