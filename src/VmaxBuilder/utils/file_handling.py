"""
Module containing functions for file handling operations, namely saving with tries for
many different datatypes.
"""

import json
import warnings
from collections.abc import Sequence
from enum import Enum
from pathlib import Path
from pickle import dump as pickle_dump
from pickle import load as pickle_load
from typing import Any

try:
    import tomllib
except ImportError:
    # For Python < 3.11, use the backport package
    import tomli as tomllib  # ty: ignore[unresolved-import]

import pandas as pd
import plotly.graph_objects as go
from pyreadr import read_r

from .custom_logging import decorator_provide_time_information_2


def get_project_root(start_path: str | Path | None = None) -> Path:
    """
    Return the project root directory as a :class:`~pathlib.Path`.

    Primary strategy
    ----------------
    Walk upwards from *start_path* (defaults to this file's directory) until a
    ``pyproject.toml`` is found whose ``[project] name`` field is set.  The
    directory that contains that file is returned as the project root.

    Fallback strategy
    -----------------
    If no ``pyproject.toml`` with a project name is found, walk upwards until a
    directory named ``src`` is encountered and return its parent.

    Raises
    ------
    RuntimeError
        If neither a ``pyproject.toml`` nor a ``src`` directory can be found
        while walking upwards.
    """
    start = (
        Path(start_path).resolve()
        if start_path is not None
        else Path(__file__).resolve().parent
    )
    current = start if start.is_dir() else start.parent

    # --- Primary: locate pyproject.toml with a project name ---
    node = current
    while True:
        pyproject = node / "pyproject.toml"
        if pyproject.is_file():
            try:
                with pyproject.open("rb") as fh:
                    data = tomllib.load(fh)
                if data.get("project", {}).get("name"):
                    return node
            except Exception:
                pass  # malformed toml — keep walking
        parent = node.parent
        if parent == node:
            break
        node = parent

    # --- Fallback: find 'src' and return its parent ---
    node = current
    while True:
        if node.name.lower() == "src":
            return node.parent
        parent = node.parent
        if parent == node:
            raise RuntimeError(
                f"Could not find a pyproject.toml with a project name, nor a 'src' "
                f"directory, while walking upwards from '{start}'."
            )
        node = parent


@decorator_provide_time_information_2
def load_existing_file_based_on_extension(  # noqa: C901
    location: str | Path,
    index_col: int | str | None = None,
    is_cobra_model: bool = False,
) -> object:
    """Generated: validation needed.

    Description:
        Load existing file by extension and return deserialized object.

    Args:
        location (str | Path): File location.
        index_col (int | str | None): Optional index column for tabular files.
        is_cobra_model (bool): When True, load COBRA model formats through cobra readers.

    Returns:
        object: Loaded file content.

    Raises:
        ValueError: If file extension is unsupported.
    """
    print(
        f"Loading file from {location} with"
        f"index_col={index_col} and is_cobra_model={is_cobra_model}"
    )
    location_path = Path(location)

    if is_cobra_model:
        from cobra.io import load_json_model, load_matlab_model, read_sbml_model

        if location_path.suffix == ".json":
            return load_json_model(str(location_path))
        if location_path.suffix == ".xml":
            return read_sbml_model(str(location_path))
        if location_path.suffix == ".mat":
            return load_matlab_model(str(location_path))

    if location_path.suffix == ".json":
        with location_path.open("r", encoding="utf-8") as json_file:
            data = json.load(json_file)
        try:
            return pd.DataFrame(data)
        except ValueError:
            return data
    if location_path.suffix == ".pkl":
        with location_path.open("rb") as pickle_file:
            data = pickle_load(pickle_file)
        try:
            return pd.read_pickle(location_path)
        except ValueError:
            return data
    if location_path.suffix == ".csv":
        return pd.read_csv(
            location_path,
            index_col=index_col,
        )
    if location_path.suffix == ".tsv":
        return pd.read_csv(location_path, sep="\t")
    if location_path.suffix == ".txt":
        try:
            return pd.read_csv(location_path, sep="\t")
        except pd.errors.ParserError:
            return location_path.read_text(encoding="utf-8")
    if location_path.suffix == ".xlsx":
        return pd.read_excel(location_path)
    if location_path.suffix == ".feather":
        df = pd.read_feather(location_path)
        # if index_col is not None:
        #     if index_col not in df.columns and isinstance(index_col, int):
        #         index_col = df.columns[index_col]
        #     df.set_index(index_col, inplace=True)
        return df
    if location_path.suffix == ".parquet":
        return pd.read_parquet(location_path)
    if location_path.suffix == ".rds":
        # we use pyreadr
        result = read_r(str(location_path))
        if len(result) == 1:
            return next(iter(result.values()))
        # find something that looks like a dataframe
        for value in result.values():
            try:
                pd.DataFrame(value)
                return pd.DataFrame(value)
            except Exception:
                continue
        raise ValueError(f"Could not find a dataframe in the RDS file at {location_path}")

    raise ValueError(f"Unsupported file extension for {location_path}")


@decorator_provide_time_information_2
def check_for_existing_files(
    location: str | Path,
    file_name_start: Sequence[str],
    file_name_end: Sequence[str],
) -> str | bool:
    """Generated: validation needed.

    Description:
        Check for existing file in directory using filename prefix and suffix.

    Args:
        location (str | Path): Directory to search.
        file_name_start (Sequence[str]): Accepted lowercase filename prefixes.
        file_name_end (Sequence[str]): Accepted lowercase filename suffixes.

    Returns:
        str | bool: Matching file path when found, otherwise False.
    """
    location_path = Path(location)
    if not location_path.exists():
        return False
    for file_path in location_path.iterdir():
        if not file_path.is_file():
            continue
        file_name_lower = file_path.name.lower()
        for start in file_name_start:
            for end in file_name_end:
                if file_name_lower.startswith(start) and file_name_lower.endswith(end):
                    return str(file_path)
    return False


@decorator_provide_time_information_2
def save_with_tries(  # noqa: C901
    data: Any,
    filename: str,
    extension: str | Sequence[str],
    save_dir: str | Path,
    max_tries: int = 10,
    overwrite: bool = False,
    with_index: bool = False,
    header: bool | list[str] = True,
    logger: Any | None = None,
    print_level: int | None = None,
) -> None:
    """Generated: validation needed.

    Description:
        Save supported data objects with retry and filename collision handling.

    Args:
        data (Any): Data to write.
        filename (str): Output filename without directory.
        extension (str | Sequence[str]): Target extension or extensions.
        save_dir (str | Path): Output directory.
        max_tries (int): Maximum rename retries when overwrite is disabled.
        overwrite (bool): Overwrite existing file when True.
        with_index (bool): Include index when writing tabular objects.
        header (bool | list[str]): Header flag passed to pandas writers.
        logger (Any | None): Optional logger supporting info and warning.
        print_level (int | None): Optional print level for logger.

    Returns:
        None: Function writes file to disk.

    Raises:
        TypeError: If data type is unsupported.
        ValueError: If extension is invalid for data type.
    """
    save_path = Path(save_dir)
    datatype: str | None = None
    filename = filename.replace("/", "_").replace(
        "\\", "_"
    )  # Replace slashes to avoid path issues
    datatype_extension_pairing = {
        "dataframe": ["csv", "json", "xlsx", "feather", "parquet", "pkl"],
        "series": ["csv", "json", "xlsx", "feather", "parquet", "pkl"],
        "dict": ["json", "jsonl", "txt", "pkl", "parquet"],
        "list": ["json", "jsonl", "txt", "pkl", "parquet"],
        "string": ["txt"],
        "go_figure": ["html", "png", "jpeg", "pdf"],
        "html": ["html"],
    }
    possible_extensions = {
        ext for ext_list in datatype_extension_pairing.values() for ext in ext_list
    }
    if logger is not None:
        logger.info(
            f"Saving {type(data)} to {filename} in {save_dir} with extension {extension}.",
            print_level=print_level if print_level is not None else 3,
        )
    if not isinstance(data, (pd.DataFrame, pd.Series, dict, list, str, go.Figure)):
        raise TypeError(
            f"Unsupported data type: {type(data)}. Supported types are: "
            "pd.DataFrame, pd.Series, dict, list, str."
        )
    if isinstance(data, pd.DataFrame):
        datatype = "dataframe"
    elif isinstance(data, pd.Series):
        datatype = "series"
    elif isinstance(data, dict):
        datatype = "dict"
    elif isinstance(data, list):
        datatype = "list"
    elif (
        isinstance(data, str)
        and not extension == "html"
        and "<" not in data
        and ">" not in data
    ):
        datatype = "string"
    elif isinstance(data, str) and extension == "html" and ("<" in data or ">" in data):
        datatype = "html"
    elif isinstance(data, go.Figure):
        datatype = "go_figure"
    if datatype is None:
        raise TypeError(f"Unsupported data type: {type(data)}")

    extensions = [extension] if isinstance(extension, str) else list(extension)
    original_filename = filename

    def _write_to_path(file_path: Path, current_extension: str) -> None:  # noqa: C901
        normalized_extension = (
            current_extension
            if current_extension.startswith(".")
            else f".{current_extension}"
        )
        if datatype == "dataframe":
            if normalized_extension == ".csv":
                data.to_csv(file_path, index=with_index, header=header)
            elif normalized_extension == ".json":
                data.to_json(file_path, orient="records", lines=True)
            elif normalized_extension == ".xlsx":
                data.to_excel(file_path, index=with_index, header=header)
            elif normalized_extension == ".feather":
                frame = data.copy()
                if with_index:
                    frame.reset_index(inplace=True)
                frame.to_feather(file_path)
            elif normalized_extension == ".parquet":
                data.to_parquet(file_path)
            elif normalized_extension == ".pkl":
                data.to_pickle(file_path)
        elif datatype == "series":
            if normalized_extension == ".csv":
                data.to_csv(file_path, index=with_index, header=header)
            elif normalized_extension == ".json":
                data.to_json(file_path, orient="records", lines=True)
            elif normalized_extension == ".xlsx":
                data.to_excel(file_path, index=with_index, header=header)
            elif normalized_extension == ".feather":
                frame = data.to_frame()
                if with_index:
                    frame = frame.copy()
                    frame.reset_index(inplace=True)
                frame.to_feather(file_path)
            elif normalized_extension == ".parquet":
                data.to_parquet(file_path)
            elif normalized_extension == ".pkl":
                data.to_pickle(file_path)
        elif datatype == "dict":
            if normalized_extension == ".json":
                with file_path.open("w", encoding="utf-8") as file_handle:
                    json.dump(data, file_handle)
            elif normalized_extension == ".jsonl":
                with file_path.open("w", encoding="utf-8") as file_handle:
                    for item in data:
                        file_handle.write(json.dumps(item) + "\n")
            elif normalized_extension == ".txt":
                with file_path.open("w", encoding="utf-8") as file_handle:
                    for key, value in data.items():
                        file_handle.write(f"{key}: {value}\n")
            elif normalized_extension == ".pkl":
                with file_path.open("wb") as file_handle:
                    pickle_dump(data, file_handle)
        elif datatype == "list":
            if normalized_extension == ".json":
                with file_path.open("w", encoding="utf-8") as file_handle:
                    json.dump(data, file_handle)
            elif normalized_extension == ".jsonl":
                with file_path.open("w", encoding="utf-8") as file_handle:
                    for item in data:
                        file_handle.write(json.dumps(item) + "\n")
            elif normalized_extension == ".txt":
                with file_path.open("w", encoding="utf-8") as file_handle:
                    for item in data:
                        file_handle.write(f"{item}\n")
            elif normalized_extension == ".pkl":
                with file_path.open("wb") as file_handle:
                    pickle_dump(data, file_handle)
        elif datatype == "string":
            file_path.write_text(data, encoding="utf-8")
        elif datatype == "go_figure":
            if normalized_extension == ".html":
                data.write_html(file_path)
            elif normalized_extension in [".png", ".jpeg"]:
                data.write_image(file_path)
            elif normalized_extension == ".pdf":
                data.write_image(file_path, format="pdf")
            elif normalized_extension == ".json":
                data.write_json(file_path)
        elif datatype == "html":
            file_path.write_text(data, encoding="utf-8")

    for current_extension in extensions:
        extension_in_filename = Path(original_filename).suffix.lstrip(".")
        if (
            extension_in_filename in possible_extensions
            and extension_in_filename != current_extension.lstrip(".")
        ):
            warn_message = (
                f"Extension in filename '{extension_in_filename}' does not match "
                f"the specified extension '{current_extension}'. Using provided filename: "
                f"{original_filename}."
            )
            if logger is None:
                warnings.warn(warn_message, stacklevel=2)
            else:
                logger.warning(warn_message)
            current_extension = f".{extension_in_filename}"
            filename = f"{Path(original_filename).stem}.{current_extension.lstrip('.')}"

        save_path.mkdir(parents=True, exist_ok=True)

        valid_extensions = datatype_extension_pairing[datatype]
        if (
            current_extension not in valid_extensions
            and current_extension.lstrip(".") not in valid_extensions
        ):
            raise ValueError(
                f"Extension '{current_extension}' is not valid for data type '{datatype}'. "
                f"Valid extensions are: {valid_extensions}."
            )

        normalized_extension = (
            current_extension
            if current_extension.startswith(".")
            else f".{current_extension}"
        )
        if not filename.endswith(normalized_extension):
            filename = f"{original_filename}{normalized_extension}"

        file_path = save_path / filename
        filename_without_extension = file_path.stem

        if overwrite:
            try:
                _write_to_path(file_path, normalized_extension)
            except Exception as exc:
                error_message = (
                    f"Failed to save file '{file_path}' after {max_tries} attempts. "
                    f"Error: {exc}"
                )
                if logger is None:
                    warnings.warn(error_message, stacklevel=2)
                else:
                    logger.warning(error_message)
                raise Exception(error_message) from exc
            continue

        for attempt_index in range(max_tries):
            candidate_path = (
                file_path
                if attempt_index == 0
                else save_path
                / f"{filename_without_extension}_{attempt_index}{normalized_extension}"
            )
            if candidate_path.exists() and attempt_index < max_tries - 1:
                continue
            try:
                _write_to_path(candidate_path, normalized_extension)
                break
            except Exception as exc:
                if attempt_index < max_tries - 1:
                    continue
                error_message = (
                    f"Failed to save file '{candidate_path}' after {max_tries} attempts. "
                    f"Error: {exc}"
                )
                if logger is None:
                    warnings.warn(error_message, stacklevel=2)
                else:
                    logger.warning(error_message)
                raise Exception(error_message) from exc


def _save_tabular_payload(
    *,
    payload: pd.DataFrame | pd.Series,
    filename: str,
    save_directory: Path,
    include_index: bool,
) -> Path:
    """Generated: validation needed.

    Description:
        Save tabular runtime payload as CSV for user inspection.

    Args:
        payload (pd.DataFrame | pd.Series): Tabular payload.
        filename (str): Output filename stem.
        save_directory (Path): Target directory.
        include_index (bool): Whether to include index column.

    Returns:
        Path: Saved CSV path.
    """

    save_with_tries(
        data=payload,
        filename=filename,
        extension="csv",
        save_dir=save_directory,
        overwrite=True,
        with_index=include_index,
    )
    return save_directory / f"{filename}.csv"


def _save_json_payload(
    *,
    payload: dict[str, Any] | list[Any],
    filename: str,
    save_directory: Path,
) -> Path:
    """Generated: validation needed.

    Description:
        Save JSON-serialisable runtime payload.

    Args:
        payload (dict[str, Any] | list[Any]): JSON-safe payload.
        filename (str): Output filename stem.
        save_directory (Path): Target directory.

    Returns:
        Path: Saved JSON path.
    """

    save_with_tries(
        data=payload,
        filename=filename,
        extension="json",
        save_dir=save_directory,
        overwrite=True,
    )
    return save_directory / f"{filename}.json"


def _save_text_payload(
    *,
    payload: str,
    filename: str,
    save_directory: Path,
) -> Path:
    """Generated: validation needed.

    Description:
        Save scalar runtime payload as plain text.

    Args:
        payload (str): Text payload.
        filename (str): Output filename stem.
        save_directory (Path): Target directory.

    Returns:
        Path: Saved text path.
    """

    save_with_tries(
        data=payload,
        filename=filename,
        extension="txt",
        save_dir=save_directory,
        overwrite=True,
    )
    return save_directory / f"{filename}.txt"


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
