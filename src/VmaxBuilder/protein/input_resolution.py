"""Generated: validation needed.

Description:
    Shared dataframe input resolution helpers for protein-stage submodules.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from VmaxBuilder.config.dataclasses import APIConfig
from VmaxBuilder.config.validation import ConfigurationError
from VmaxBuilder.core.protocols import Scaffold
from VmaxBuilder.utils.file_handling import load_existing_file_based_on_extension


def resolve_dataframe_input(
    scaffold: Scaffold,
    config: APIConfig,
    *,
    input_key: str,
) -> pd.DataFrame | None:
    """Generated: validation needed.

    Description:
        Resolve one dataframe input from scaffold, in-memory config,
        explicit path, or search roots.

    Args:
        scaffold (Scaffold): Shared pipeline scaffold.
        config (APIConfig): Root API configuration.
        input_key (str): Logical input key, e.g. expression, ptr, proteomics.

    Returns:
        pd.DataFrame | None: Resolved dataframe or None when absent.

    Raises:
        ConfigurationError: When provided input is not a dataframe.

    Modifies:
        scaffold["inputs"] when a dataframe is resolved from config or disk.
    """

    input_payload = scaffold.setdefault("inputs", {})
    if input_key in input_payload:
        input_value = input_payload[input_key]
        if not isinstance(input_value, pd.DataFrame):
            raise ConfigurationError(
                f"Input '{input_key}' must be pandas.DataFrame; got "
                f"{type(input_value).__name__}."
            )
        return input_value

    in_memory_inputs = config.loading.get_effective_in_memory_inputs()
    if input_key in in_memory_inputs:
        input_value = in_memory_inputs[input_key]
        if not isinstance(input_value, pd.DataFrame):
            raise ConfigurationError(
                f"In-memory input '{input_key}' must be pandas.DataFrame; got "
                f"{type(input_value).__name__}."
            )
        input_payload[input_key] = input_value
        return input_value

    explicit_paths = config.loading.get_effective_exact_paths()
    input_path = explicit_paths.get(input_key)
    if input_path is not None:
        resolved_input_path = resolve_input_file_path(
            Path(input_path),
            input_key=input_key,
            config=config,
        )
        loaded_value = load_existing_file_based_on_extension(
            resolved_input_path,
            index_col=0,
        )
        if not isinstance(loaded_value, pd.DataFrame):
            raise ConfigurationError(
                f"Loaded input '{input_key}' from '{resolved_input_path}' is not "
                "pandas.DataFrame."
            )
        loaded_value = normalize_loaded_dataframe(loaded_value)
        input_payload[input_key] = loaded_value
        return loaded_value

    for search_root in config.loading.iter_search_roots(input_key):
        try:
            resolved_input_path = resolve_input_file_path(
                Path(search_root),
                input_key=input_key,
                config=config,
            )
        except ConfigurationError:
            continue
        loaded_value = load_existing_file_based_on_extension(
            resolved_input_path,
            index_col=0,
        )
        if not isinstance(loaded_value, pd.DataFrame):
            raise ConfigurationError(
                f"Loaded input '{input_key}' from '{resolved_input_path}' is not "
                "pandas.DataFrame."
            )
        loaded_value = normalize_loaded_dataframe(loaded_value)
        input_payload[input_key] = loaded_value
        return loaded_value

    return None


def resolve_input_file_path(
    candidate_path: Path,
    *,
    input_key: str,
    config: APIConfig,
) -> Path:
    """Generated: validation needed.

    Description:
        Resolve concrete file path for one dataframe input from file or directory candidate.

    Args:
        candidate_path (Path): File or directory candidate path.
        input_key (str): Logical input key.
        config (APIConfig): Root API configuration.

    Returns:
        Path: Resolved file path.

    Raises:
        ConfigurationError: When no matching input file exists.
    """

    allowed_extensions = {
        extension.lower() for extension in config.loading.get_discovery_extensions(input_key)
    }
    filename_prefixes = tuple(
        prefix.lower() for prefix in config.loading.get_discovery_prefixes(input_key)
    )

    if candidate_path.is_file():
        if candidate_path.suffix.lower() not in allowed_extensions:
            raise ConfigurationError(
                f"Input '{input_key}' has unsupported extension '{candidate_path.suffix}'."
            )
        return candidate_path

    if candidate_path.is_dir():
        candidates = sorted(
            file_path
            for file_path in candidate_path.iterdir()
            if file_path.is_file()
            and file_path.name.lower().startswith(filename_prefixes)
            and file_path.suffix.lower() in allowed_extensions
        )
        if candidates:
            return candidates[0]

    raise ConfigurationError(
        f"Could not resolve input '{input_key}' from '{candidate_path}'."
    )


def normalize_loaded_dataframe(loaded_df: pd.DataFrame) -> pd.DataFrame:
    """Generated: validation needed.

    Description:
        Normalize loaded dataframe index when loader leaves identifier column in values.

    Args:
        loaded_df (pd.DataFrame): Loaded dataframe from file.

    Returns:
        pd.DataFrame: Normalized dataframe with identifier index when detectable.
    """

    if loaded_df.empty or not isinstance(loaded_df.index, pd.RangeIndex):
        return loaded_df
    first_column = loaded_df.columns[0]
    first_series = loaded_df[first_column]
    should_promote_index = (
        str(first_column).lower().startswith("unnamed") or first_series.dtype == object
    ) and first_series.is_unique
    if not should_promote_index:
        return loaded_df

    normalized_df = loaded_df.copy()
    normalized_df.set_index(first_column, inplace=True)
    return normalized_df
