"""
Module containing functions for file handling operations, namely saving with tries for
many different datatypes.
"""

import json
import os

try:
    import tomllib
except ImportError:
    # For Python < 3.11, use the backport package
    import tomli as tomllib  # ty: ignore[unresolved-import]
import warnings
from pathlib import Path
from pickle import dump as pickle_dump
from pickle import load as pickle_load
from typing import List, Optional, Union

import pandas as pd
import plotly.graph_objects as go
from cobrapy_fork._cobra import load_matlab_model, save_json_model
from cobrapy_fork.io import load_json_model, read_sbml_model
from pyreadr import read_r
from SWAMP.utils.custom_logging import decorator_provide_time_information_2

# todo add kcat_assigning.KcatGPRAssigner.(load_existing_file_based_on_extension and check for existing files)
# to the utils.file_handling module


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
def load_existing_file_based_on_extension(
    location: str,
    index_col: Optional[Union[int, str]] = None,
    is_cobra_model: Optional[bool] = False,
):
    """ """
    if is_cobra_model:
        if location.endswith(".json"):
            return load_json_model(location)
        elif location.endswith(".xml"):
            return read_sbml_model(location)
        elif location.endswith(".mat"):
            return load_matlab_model(location)

    if location.endswith(".json"):
        with open(location, "r") as json_file:
            data = json.load(json_file)
        try:
            return pd.DataFrame(data)
        except ValueError:
            return data
    elif location.endswith(".pkl"):
        with open(location, "rb") as pickle_file:
            data = pickle_load(pickle_file)
        try:
            return pd.read_pickle(location)
        except ValueError:
            return data
    elif location.endswith(".csv"):
        return pd.read_csv(
            location,
            index_col=index_col,
        )
    elif location.endswith(".tsv"):
        return pd.read_csv(location, sep="\t")
    elif location.endswith(".txt"):
        try:
            return pd.read_csv(location, sep="\t")
        except pd.errors.ParserError:
            with open(location, "r") as f:
                return f.read()
    elif location.endswith(".xlsx"):
        return pd.read_excel(location)
    elif location.endswith(".feather"):
        df = pd.read_feather(location)
        # if index_col is not None:
        #     if index_col not in df.columns and isinstance(index_col, int):
        #         index_col = df.columns[index_col]
        #     df.set_index(index_col, inplace=True)
        return df
    elif location.endswith(".parquet"):
        return pd.read_parquet(location)
    elif location.endswith(".rds"):
        # we use pyreadr
        result = read_r(location)
        if len(result) == 1:
            return next(iter(result.values()))
        # find something that looks like a dataframe
        for value in result.values():
            try:
                pd.DataFrame(value)
                return pd.DataFrame(value)
            except Exception:
                continue
        raise ValueError(f"Could not find a dataframe in the RDS file at {location}")

    else:
        raise ValueError(f"Unsupported file extension for {location}")


@decorator_provide_time_information_2
def check_for_existing_files(
    location: str,
    file_name_start: List[str],
    file_name_end: List[str],
):
    """
    Checks for existing files in a given directory based on specified start and end patterns.
    """
    if not os.path.exists(location):
        return False
    for start in file_name_start:
        for end in file_name_end:
            for file_name in os.listdir(location):
                file_name_lower = file_name.lower()
                if file_name_lower.startswith(start) and file_name_lower.endswith(end):
                    return os.path.join(location, file_name)
    return False


@decorator_provide_time_information_2
def save_with_tries(
    data: object,
    filename: str,
    extension: Union[str, List[str]],
    save_dir: str,
    max_tries: Optional[int] = 10,
    overwrite: Optional[bool] = False,
    with_index: Optional[bool] = False,
    header: Optional[bool] = True,
    logger: Optional[object] = None,
    print_level: Optional[int] = None,
) -> None:
    # todo create registry pattern for saving and loading different data types
    #  https://www.youtube.com/watch?v=g7EGMWvJ1fI
    # todo allow extensions to be a list and then save for all extension types
    datatype = None
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
    possible_extensions = []
    for ext_list in datatype_extension_pairing.values():
        possible_extensions.extend(ext_list)
    possible_extensions = list(set(possible_extensions))
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

    extensions = [ext for ext in extension] if isinstance(extension, list) else [extension]
    original_filename = filename
    for extension in extensions:
        extension_in_filename = original_filename.split(".")[-1]
        if extension_in_filename in possible_extensions:
            if extension_in_filename != extension:
                warn_message = (
                    f"Extension in filename '{extension_in_filename}' does not match "
                    f"the specified extension '{extension}'. Using provided filename: "
                    f"{original_filename}."
                )
                warnings.warn(warn_message) if logger is None else logger.warning(
                    warn_message
                )
                extension = "." + extension_in_filename
                filename = original_filename.split(".")[0] + "." + extension
        if not os.path.exists(save_dir):
            warning_message = f"Directory '{save_dir}' does not exist. Creating it."
            warnings.warn(warning_message) if logger is None else logger.warning(
                warning_message
            )
            os.makedirs(save_dir)

        if extension not in datatype_extension_pairing[datatype]:
            raise ValueError(
                f"Extension '{extension}' is not valid for data type '{datatype}'. "
                f"Valid extensions are: {datatype_extension_pairing[datatype]}."
            )
        if "." not in extension:
            extension = "." + extension
        if not filename.endswith(extension):
            filename = original_filename + extension
        file_path = os.path.join(save_dir, filename)

        if not overwrite:
            filename_without_extension = filename.split(".")[0]
            for i in range(max_tries):
                if os.path.exists(file_path):
                    file_path = os.path.join(
                        save_dir, filename_without_extension + f"_{i + 1}" + extension
                    )
                try:
                    if datatype == "dataframe":
                        if extension == ".csv":
                            data.to_csv(file_path, index=with_index, header=header)
                        elif extension == ".json":
                            data.to_json(file_path, orient="records", lines=True)
                        elif extension == ".xlsx":
                            data.to_excel(file_path, index=with_index, header=header)
                        elif extension == ".feather":
                            if with_index:
                                data = data.copy()
                                data.reset_index(inplace=True)
                            data.to_feather(file_path)
                        elif extension == ".parquet":
                            data.to_parquet(file_path)
                        elif extension == ".pkl":
                            data.to_pickle(file_path)
                    elif datatype == "series":
                        if extension == ".csv":
                            data.to_csv(file_path, index=with_index, header=header)
                        elif extension == ".json":
                            data.to_json(file_path, orient="records", lines=True)
                        elif extension == ".xlsx":
                            data.to_excel(file_path, index=with_index, header=header)
                        elif extension == ".feather":
                            data = data.to_frame()
                            if with_index:
                                data = data.copy()
                                data.reset_index(inplace=True)
                            data.to_feather(file_path)
                        elif extension == ".parquet":
                            data.to_parquet(file_path)
                        elif extension == ".pkl":
                            data.to_pickle(file_path)
                    elif datatype == "dict":
                        if extension == ".json":
                            with open(file_path, "w") as f:
                                json.dump(data, f)
                        elif extension == ".jsonl":
                            with open(file_path, "w") as f:
                                for item in data:
                                    f.write(json.dumps(item) + "\n")
                        elif extension == ".txt":
                            with open(file_path, "w") as f:
                                for key, value in data.items():
                                    f.write(f"{key}: {value}\n")
                        elif extension == ".pkl":
                            with open(file_path, "wb") as f:
                                pickle_dump(data, f)
                    elif datatype == "list":
                        if extension == ".json":
                            with open(file_path, "w") as f:
                                json.dump(data, f)
                        elif extension == ".jsonl":
                            with open(file_path, "w") as f:
                                for item in data:
                                    f.write(json.dumps(item) + "\n")
                        elif extension == ".txt":
                            with open(file_path, "w") as f:
                                for key, value in data.items():
                                    f.write(f"{key}: {value}\n")
                        elif extension == ".pkl":
                            with open(file_path, "wb") as f:
                                pickle_dump(data, f)
                    elif datatype == "string":
                        with open(file_path, "w") as f:
                            f.write(data)
                    elif datatype == "go_figure":
                        if extension == ".html":
                            data.write_html(file_path)
                        elif extension in [".png", ".jpeg"]:
                            data.write_image(file_path)
                        elif extension == ".pdf":
                            data.write_image(file_path, format="pdf")
                        elif extension == ".json":
                            data.write_json(file_path)
                    elif datatype == "html":
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(data)

                    break
                except Exception as e:
                    if i < max_tries - 1:
                        file_path = os.path.join(
                            save_dir,
                            filename_without_extension + f"_{i + 1}" + extension,
                        )
                    else:
                        error_message = (
                            f"Failed to save file '{file_path}' after {max_tries} attempts. "
                            f"Error: {e}"
                        )
                        warnings.warn(error_message) if logger is None else logger.warning(
                            error_message
                        )
                        raise Exception(error_message) from e
        elif overwrite or not os.path.exists(file_path):
            try:
                if datatype == "dataframe":
                    if extension == ".csv":
                        data.to_csv(file_path, index=with_index, header=header)
                    elif extension == ".json":
                        data.to_json(file_path, orient="records", lines=True)
                    elif extension == ".xlsx":
                        data.to_excel(file_path, index=with_index, header=header)
                    elif extension == ".feather":
                        if with_index:
                            data = data.copy()
                            data.reset_index(inplace=True)
                        data.to_feather(file_path)
                    elif extension == ".parquet":
                        data.to_parquet(file_path)
                    elif extension == ".pkl":
                        data.to_pickle(file_path)
                elif datatype == "series":
                    if extension == ".csv":
                        data.to_csv(file_path, index=with_index, header=header)
                    elif extension == ".json":
                        data.to_json(file_path, orient="records", lines=True)
                    elif extension == ".xlsx":
                        data.to_excel(file_path, index=with_index, header=header)
                    elif extension == ".feather":
                        data = data.to_frame()
                        # convert index column to first column if with_index is True
                        if with_index:
                            data = data.copy()
                            data.reset_index(inplace=True)
                        data.to_feather(file_path)
                    elif extension == ".parquet":
                        data.to_parquet(file_path)
                    elif extension == ".pkl":
                        data.to_pickle(file_path)
                elif datatype == "dict":
                    if extension == ".json":
                        with open(file_path, "w") as f:
                            json.dump(data, f)
                    elif extension == ".jsonl":
                        with open(file_path, "w") as f:
                            for item in data:
                                f.write(json.dumps(item) + "\n")
                    elif extension == ".txt":
                        with open(file_path, "w") as f:
                            for key, value in data.items():
                                f.write(f"{key}: {value}\n")
                    elif extension == ".pkl":
                        with open(file_path, "wb") as f:
                            pickle_dump(data, f)
                elif datatype == "list":
                    if extension == ".json":
                        with open(file_path, "w") as f:
                            json.dump(data, f)
                    elif extension == ".jsonl":
                        with open(file_path, "w") as f:
                            for item in data:
                                f.write(json.dumps(item) + "\n")
                    elif extension == ".txt":
                        with open(file_path, "w") as f:
                            for key, value in data.items():
                                f.write(f"{key}: {value}\n")
                    elif extension == ".pkl":
                        with open(file_path, "wb") as f:
                            pickle_dump(data, f)
                elif datatype == "string":
                    with open(file_path, "w") as f:
                        f.write(data)
                elif datatype == "go_figure":
                    if extension == ".html":
                        data.write_html(file_path)
                    elif extension in [".png", ".jpeg"]:
                        data.write_image(file_path)
                    elif extension == ".pdf":
                        data.write_image(file_path, format="pdf")
                    elif extension == ".json":
                        data.write_json(file_path)
                elif datatype == "html":
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(data)
            except Exception as e:
                error_message = (
                    f"Failed to save file '{file_path}' after {max_tries} attempts. "
                    f"Error: {e}"
                )
                warnings.warn(error_message) if logger is None else logger.warning(
                    error_message
                )
                raise Exception(error_message) from e
