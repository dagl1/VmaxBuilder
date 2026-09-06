"""
Module containing functions for file handling operations, namely saving with tries for
many different datatypes.
"""

import json
from pathlib import Path
from pickle import dump as pickle_dump

from cobra.core.model import Model

from VmaxBuilder.utils.iterables import make_json_serializable

try:
    import tomllib
except ImportError:
    # For Python < 3.11, use the backport package
    import tomli as tomllib  # ty: ignore[unresolved-import]

from dataclasses import dataclass
from enum import Enum
from typing import Any

import pandas as pd
import plotly.graph_objects as go


@dataclass(frozen=True)
class TypeInfo:
    pytype: type | tuple[type, ...]
    extensions: tuple[str, ...]


@dataclass
class SaveContext:
    with_index: bool = False
    header: bool | list[str] = True
    plot_size: tuple[int, int] | None = (3200, 2800)  # Default width and height for plots

    def __post_init__(self):
        if not isinstance(self.with_index, bool):
            raise TypeError(f"with_index must be a boolean, got {type(self.with_index)}")
        if not isinstance(self.header, (bool, list)):
            raise TypeError(
                f"header must be a boolean or list of strings, got {type(self.header)}"
            )
        if self.plot_size is None:
            self.plot_size = (1600, 1200)  # Default width and height for plots
        if not isinstance(self.plot_size, tuple) or len(self.plot_size) != 2:
            raise TypeError(
                f"plot_size must be a tuple of two integers, got {self.plot_size}"
            )
        if not all(isinstance(dim, int) for dim in self.plot_size):
            raise TypeError(f"plot_size dimensions must be integers, got {self.plot_size}")


def save_dataframe(
    data: pd.DataFrame,
    path: Path,
    extension: str,
    context: SaveContext,
) -> None:
    with_index = context.with_index
    header = context.header
    if extension == "csv":
        data.to_csv(path, index=with_index, header=header)
    elif extension == "json":
        data.to_json(path, orient="records", lines=True)
    elif extension == "xlsx":
        data.to_excel(path, index=with_index, header=header)
    elif extension == "feather":
        frame = data.copy()
        if with_index:
            frame.reset_index(inplace=True)
        frame.to_feather(path)
    elif extension == "parquet":
        data.to_parquet(path)
    elif extension == "pkl":
        data.to_pickle(path)


def save_series(
    data: pd.Series,
    path: Path,
    extension: str,
    context: SaveContext,
) -> None:
    with_index = context.with_index
    header = context.header

    if extension == "csv":
        data.to_csv(path, index=with_index, header=header)
    elif extension == "json":
        data.to_json(path, orient="records", lines=True)
    elif extension == "xlsx":
        data.to_excel(path, index=with_index, header=header)
    elif extension == "feather":
        frame = data.to_frame()
        if with_index:
            frame = frame.copy()
            frame.reset_index(inplace=True)
        frame.to_feather(path)
    elif extension == "parquet":
        data.to_parquet(path)
    elif extension == "pkl":
        data.to_pickle(path)


def save_dict(
    data: dict,
    path: Path,
    extension: str,
    context: SaveContext,
) -> None:
    data = make_json_serializable(data)
    if extension == "json":
        with path.open("w", encoding="utf-8") as file_handle:
            json.dump(data, file_handle)
    elif extension == "jsonl":
        with path.open("w", encoding="utf-8") as file_handle:
            for item in data:
                file_handle.write(json.dumps(item) + "\n")
    elif extension == "txt":
        with path.open("w", encoding="utf-8") as file_handle:
            for key, value in data.items():
                file_handle.write(f"{key}: {value}\n")
    elif extension == "pkl":
        with path.open("wb") as file_handle:
            pickle_dump(data, file_handle)


def save_list(
    data: list | tuple | set,
    path: Path,
    extension: str,
    context: SaveContext,
) -> None:
    if isinstance(data, set):
        data = list(data)

    data = make_json_serializable(data)
    if extension == "json":
        with path.open("w", encoding="utf-8") as file_handle:
            json.dump(data, file_handle)
    elif extension == "jsonl":
        with path.open("w", encoding="utf-8") as file_handle:
            for item in data:
                file_handle.write(json.dumps(item) + "\n")
    elif extension == "txt":
        with path.open("w", encoding="utf-8") as file_handle:
            for item in data:
                file_handle.write(f"{item}\n")
    elif extension == "pkl":
        with path.open("wb") as file_handle:
            pickle_dump(data, file_handle)


def save_string(
    data: str,
    path: Path,
    extension: str,
    context: SaveContext,
) -> None:
    path.write_text(data, encoding="utf-8")


def save_html(
    data: str,
    path: Path,
    extension: str,
    context: SaveContext,
) -> None:
    path.write_text(data, encoding="utf-8")


def save_go_figure(
    data: go.Figure,
    path: Path,
    extension: str,
    context: SaveContext,
) -> None:
    size = context.plot_size
    if size is not None:
        (width, height) = size
    else:
        size = (1600, 1200)
    if extension == "html":
        data.write_html(path)
    elif extension in ["png", "jpeg"]:
        data.write_image(path, format=extension, width=width, height=height)
    elif extension == "pdf":
        data.write_image(path, format="pdf", width=width, height=height)
    elif extension == "json":
        data.write_json(path)
    elif extension == "svg":
        data.write_image(path, format="svg", width=width, height=height)


def save_cobra_model(
    data: Model,
    path: Path,
    extension: str,
    context: SaveContext,
) -> None:
    """Generated: validation needed.

    Description:
        Save COBRA model using appropriate writer based on extension.

    Args:
        cobra_model (Any): COBRA model object.
        filename (str): Output filename without directory.
        extension (str): Target extension.
        save_dir (str | Path): Output directory.
        overwrite (bool): Overwrite existing file when True.

    Returns:
        None: Function writes file to disk.

    Raises:
        ValueError: If extension is invalid for COBRA model.
    """
    valid_extensions = ["json", "xml", "yml", "yaml", "mat"]
    filepath_as_str = str(path)
    from cobra.io import save_json_model, save_matlab_model, save_yaml_model, write_sbml_model

    match extension:
        case "json":
            save_json_model(data, filepath_as_str)
        case "xml":
            write_sbml_model(data, filepath_as_str)
        case "yml" | ".yaml":
            save_yaml_model(data, filepath_as_str)
        case "mat":
            save_matlab_model(data, filepath_as_str)
        case _:
            raise ValueError(
                f"Extension '{extension}' is not valid for COBRA model. "
                f"Valid extensions are: {valid_extensions}."
            )


def _make_json_safe(cls, value: Any) -> Any:
    """Generated: validation needed.

    Description:
        Convert nested runtime payloads into JSON-safe builtin values.

    Args:
        value (Any): Runtime payload value.

    Returns:
        Any: JSON-safe builtin representation.
    """

    if isinstance(value, dict):
        return {
            str(key): cls._make_json_safe(nested_value) for key, nested_value in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [cls._make_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, pd.Index):
        return [cls._make_json_safe(item) for item in value.tolist()]
    if isinstance(value, pd.Series):
        return cls._make_json_safe(value.to_dict())
    if hasattr(value, "item") and callable(value.item):
        try:
            return value.item()
        except (TypeError, ValueError):
            pass
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _build_output_signature(output_directories: tuple[Path, ...]) -> tuple[str, ...]:
    """Generated: validation needed.

    Description:
        Build stable output-directory signature used for output re-prime checks.

    Args:
        output_directories (tuple[Path, ...]): Candidate output directories.

    Returns:
        tuple[str, ...]: Sorted normalized output path strings.
    """

    return tuple(sorted(str(directory.resolve()) for directory in output_directories))
