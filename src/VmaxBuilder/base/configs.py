from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Literal

from VmaxBuilder.base.config_enum import MODEL_IMPLEMENTATIONS
from VmaxBuilder.config.enums import PrimaryOutputFormat
from VmaxBuilder.utils.type_hinting import data


@dataclass(frozen=True)
class StageLoadingInfo:
    stage_name: str
    directories: list[Path | str] | None | Path | str = None
    filepaths: dict[str, Path | str] | None = None


@dataclass(frozen=True)
class Stages:
    model_implementation: MODEL_IMPLEMENTATIONS
    model_loading_info: StageLoadingInfo
    # allocation_stage: str
    # protein_stage: str


@dataclass
class ImplementationConfig:
    pass


@dataclass
class Paths:
    # ensure not mutable by user, only through set_results_dir method
    _results_dir: Path = field(init=True, repr=False)

    diagnostics_dir: Path = field(init=False)
    artifacts_dir: Path = field(init=False)
    metadata_dir: Path = field(init=False)
    outputs_dir: Path = field(init=False)

    def __post_init__(self):
        self.results_dir = self._results_dir

    @property
    def results_dir(self) -> Path:
        return self._results_dir

    @results_dir.setter
    def results_dir(self, path: Path):
        path = Path(path).expanduser().resolve()

        self._results_dir = path
        self.diagnostics_dir = path / "diagnostics"
        self.artifacts_dir = path / "artifacts"
        self.metadata_dir = path / "metadata"
        self.outputs_dir = path / "outputs"

        for p in (
            self.results_dir,
            self.diagnostics_dir,
            self.artifacts_dir,
            self.metadata_dir,
            self.outputs_dir,
        ):
            p.mkdir(parents=True, exist_ok=True)


@dataclass
class RunConfig:
    output_dir: Path = Path.cwd() / "data/results/"
    run_name: str = "VmaxResults"  # The results will be saved in a directory by this name in
    # the output_dir. If create_dynamically_named_results is True,
    # the run_name will be created from the final directory of each
    # stage's input directory, joined by underscores.
    # If False, the run_name will be used as is.
    create_dynamically_named_results: bool = False
    active_stages: list[str] | str = "all"  # If None, all stages are active.
    # If a list of stage names, only those stages will be run.
    primary_output_format: PrimaryOutputFormat = PrimaryOutputFormat.FEATHER
    write_additional_csv: bool = False
    run_input_validation: bool = True
    run_output_validation: bool = True
    run_diagnostics: bool = True
    print_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"


@dataclass
class PathInfo:
    stage_name: str
    directories: list[Path] = field(default_factory=list)
    filepaths: dict[str, Path] = field(default_factory=dict)

    def __repr__(self):
        return (
            f"PathInfo(stage_name={self.stage_name}, "
            f"directories={self.directories},"
            f"filepaths={self.filepaths})"
        )


@dataclass
class DiscoveredInput:
    input_name: str
    filepath: Path | None

    exists: bool

    source: Literal[
        "explicit_filepath",
        "directory_search",
        "scaffold_only",
    ]

    warning: str | None = None


@dataclass
class FullConfig:
    model: ImplementationConfig
    run: RunConfig
    paths: Paths


@dataclass(frozen=True)
class InputSpec:
    """
    Scaffold is checked first, then files are checked if not found in scaffold.
    If no scaffold key, and file key present,
    loader is called with file key to load the input.
    """

    name: str
    data_type: type | None = None
    optional: bool = False
    scaffold_key: str | None = None  # scaffold key for loading from scaffold
    loader: Callable | None = None  # file → object loader
    loader_args: dict[str, Any] | None = None  # additional args for loader
    file_key: str | None = None  # file key for loading from files
    extensions: Iterable[str] | None = None  # allowed file extensions for loading


@dataclass(frozen=True)
class OutputSpec:
    name: str
    data_type: type | None = None


@dataclass
class Scaffold:
    data: dict[str, Any]

    def get(self, key: str): ...
    def set(self, key: str, value: Any): ...
