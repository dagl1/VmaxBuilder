"""
Module containing functions for file handling operations, namely saving with tries for
many different datatypes.
"""

import warnings
from collections.abc import Sequence, Set
from pathlib import Path
from typing import Any, Iterable

from cobra.core.model import Model

from VmaxBuilder.utils.iterables import SortedSet

try:
    import tomllib
except ImportError:
    # For Python < 3.11, use the backport package
    import tomli as tomllib  # ty: ignore[unresolved-import]

import pandas as pd
import plotly.graph_objects as go

from VmaxBuilder.utils.file_loading import (
    LoadContext,
    load_cobra_model,
    load_csv,
    load_feather,
    load_json,
    load_parquet,
    load_pickle,
    load_rds,
    load_xlsx,
)
from VmaxBuilder.utils.file_saving import (
    SaveContext,
    TypeInfo,
    save_cobra_model,
    save_dataframe,
    save_dict,
    save_go_figure,
    save_html,
    save_list,
    save_series,
    save_string,
)

from .custom_logging import decorator_provide_time_information_2

WRITERS = {
    "dataframe": save_dataframe,
    "series": save_series,
    "dict": save_dict,
    "list": save_list,
    "string": save_string,
    "html": save_html,
    "go_figure": save_go_figure,
    "cobra_model": save_cobra_model,
}

LOADERS = {
    "csv": load_csv,
    "json": load_json,
    "pkl": load_pickle,
    "xlsx": load_xlsx,
    "feather": load_feather,
    "parquet": load_parquet,
    "rds": load_rds,
}
COBRA_LOADERS = {
    "json": load_cobra_model,
    "xml": load_cobra_model,
    "yml": load_cobra_model,
    "yaml": load_cobra_model,
    "mat": load_cobra_model,
}

TYPE_INFO = {
    "dataframe": TypeInfo(
        pd.DataFrame,
        ("csv", "json", "xlsx", "feather", "parquet", "pkl"),
    ),
    "series": TypeInfo(
        pd.Series,
        ("csv", "json", "xlsx", "feather", "parquet", "pkl"),
    ),
    "dict": TypeInfo(
        dict,
        ("json", "jsonl", "txt", "pkl"),
    ),
    "list": TypeInfo(
        (list, tuple, set, SortedSet, Set),
        ("json", "jsonl", "txt", "pkl"),
    ),
    "string": TypeInfo(
        str,
        ("txt",),
    ),
    "html": TypeInfo(
        str,
        ("html",),
    ),
    "go_figure": TypeInfo(
        go.Figure,
        ("html", "png", "jpeg", "pdf", "svg"),
    ),
    "cobra_model": TypeInfo(
        Model,
        ("json", "xml", "yml", "yaml", "mat"),
    ),
}


def candidate_paths(
    file_path: Path,
    overwrite: bool,
    max_tries: int,
):
    if overwrite:
        yield file_path
        return

    stem = file_path.stem
    suffix = file_path.suffix

    for i in range(1, max_tries + 1):
        if i == 1:
            yield file_path
        else:
            yield file_path.with_name(f"{stem}_{i}{suffix}")


def get_datatype(data: Any, extension: str) -> str:
    if isinstance(data, str):
        is_html = "<" in data or ">" in data
        return "html" if extension == "html" and is_html else "string"

    for name, info in TYPE_INFO.items():
        if name in {"string", "html"}:
            continue
        if isinstance(data, info.pytype):
            return name

    raise TypeError(f"Unsupported type: {type(data)}")


def normalize_extension(ext: str) -> str:
    return ext.removeprefix(".")


def validate_extension(datatype: str, extension: str, filename: str) -> None:
    extension = normalize_extension(extension)

    valid = TYPE_INFO[datatype].extensions

    if extension not in valid:
        raise ValueError(
            f"{extension!r} not valid for {datatype} when saving {filename}. "
            "Choose one of {valid}."
        )


def log_info(msg, logger: Any | None = None, print_level: int | None = None) -> None:
    if print_level is None:
        print_level = 3
    if logger:
        logger.info(msg, print_level=print_level)
    else:
        print(msg)


def warn(msg, logger: Any | None = None) -> None:
    if logger:
        logger.warning(msg)
    else:
        warnings.warn(msg, stacklevel=2)


def normalise_save_dir_and_filename(
    save_dir: str | Path | None,
    filename: str | Path,
    extension: str | Iterable[str] | None,
) -> tuple[Path, str, list[str]]:
    if isinstance(filename, Path):
        if save_dir is not None:
            raise ValueError("When save_dir is provided, filename must be a string.")

        save_dir = filename.parent
        if extension is None:
            extension = filename.suffix.lstrip(".")
        filename = filename.name

    elif save_dir is None:
        raise ValueError("save_dir must be provided when filename is a string.")
    else:
        save_dir = Path(save_dir)

    filename = filename.replace("/", "_").replace("\\", "_")

    if extension is None:
        raise ValueError("Extension must be provided.")

    extensions = [
        normalize_extension(e)
        for e in ([extension] if isinstance(extension, str) else extension)
    ]
    save_path = save_dir

    return save_path, filename, extensions


def resolve_filename_extension(
    filename: str,
    requested_extension: str,
    allowed_extensions: tuple[str, ...],
    logger,
) -> tuple[str, str]:
    """
    Resolve the filename and extension based on the requested extension
    and allowed extensions.

    Args:
        filename (str): The original filename.
        requested_extension (str): The requested file extension.
        allowed_extensions (tuple[str, ...]): Allowed extensions for the data type.
        logger: Logger for logging warnings.

    Returns:
        tuple[str, str]: A tuple containing the resolved filename and extension.
    """
    current_extension = Path(filename).suffix.lstrip(".")
    if current_extension in allowed_extensions:
        if current_extension != requested_extension:
            warn(
                f"Extension in filename '{current_extension}' does not match "
                f"the specified extension '{requested_extension}'. Using provided filename: "
                f"{filename}.",
                logger=logger,
            )
        return filename, current_extension
    else:
        # If the current extension is not allowed, use the requested extension
        new_filename = str(Path(filename).with_suffix(f".{requested_extension}"))
        return new_filename, requested_extension


@decorator_provide_time_information_2
def save_with_tries(  # noqa: C901
    data: Any,
    filename: str | Path,
    extension: str | Iterable[str] | None = None,
    save_dir: str | Path | None = None,
    max_tries: int = 10,
    overwrite: bool = False,
    with_index: bool = False,
    header: bool | list[str] = True,
    logger: Any | None = None,
    print_level: int | None = None,
    *args,  # for legacy purposes to ensure backward compatibility
    **kwargs,  # for legacy purposes to ensure backward compatibility
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
    (save_path, filename, extensions) = normalise_save_dir_and_filename(
        save_dir=save_dir,
        filename=filename,
        extension=extension,
    )

    datatype = get_datatype(data, extensions[0])

    for ext in extensions:
        validate_extension(datatype, ext, filename)

    possible_extensions = TYPE_INFO[datatype].extensions
    log_info(
        f"Saving {type(data)} to {filename} in {save_path} with extension {extensions}.",
        logger=logger,
        print_level=print_level,
    )

    save_path.mkdir(parents=True, exist_ok=True)
    context = SaveContext(
        with_index=with_index, header=header, plot_size=kwargs.get("plot_size", None)
    )
    for extension in extensions:
        resolved_filename, extension = resolve_filename_extension(
            filename=filename,
            requested_extension=extension,
            allowed_extensions=possible_extensions,
            logger=logger,
        )

        file_path = save_path / Path(resolved_filename).with_suffix(f".{extension}")
        for candidate in candidate_paths(file_path, overwrite, max_tries):
            if candidate.exists() and not overwrite:
                continue

            writer = WRITERS[datatype]
            writer(
                data=data,
                path=candidate,
                extension=extension,
                context=context,
            )

            break
        else:
            raise FileExistsError(
                f"Could not find a unique filename for '{filename}' with extension "
                f"'{extension}' in directory '{str(save_path)}' "
                f"after {max_tries} attempts."
            )


@decorator_provide_time_information_2
def load_existing_file_based_on_extension(  # noqa: C901
    location: str | Path,
    index_col: int | str | None = None,
    is_cobra_model: bool = False,
    logger: Any | None = None,
    print_level: int | None = None,
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
    log_info(
        f"Loading file from {location} with"
        f"index_col={index_col} and is_cobra_model={is_cobra_model}",
        logger=logger,
        print_level=print_level,
    )
    path = Path(location)
    extension = path.suffix.lstrip(".")

    loader = LOADERS.get(extension, None)
    if is_cobra_model:
        loader = COBRA_LOADERS.get(extension, None)

    if loader is None:
        raise ValueError(
            f"Unsupported file extension '{extension}' for loading. "
            f"Supported extensions are: {list(LOADERS.keys())} "
            f"and COBRA model extensions are: {list(COBRA_LOADERS.keys())}."
        )

    context = LoadContext(index_col=index_col)
    loaded_object = loader(path, context)
    return loaded_object


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


def _generate_unique_filename(
    save_dir: Path,
    filename: str,
    extension: str,
    max_tries: int = 10,
) -> str | None:
    """Generate a unique filename by appending a counter if the file already exists."""
    base_filename = Path(filename).stem
    for attempt_index in range(max_tries):
        candidate_filename = (
            f"{base_filename}_{attempt_index}{extension}"
            if attempt_index > 0
            else f"{base_filename}{extension}"
        )
        candidate_path = save_dir / candidate_filename
        if not candidate_path.exists():
            return candidate_filename
