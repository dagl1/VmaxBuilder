from dataclasses import InitVar, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Iterable, Literal, TypeAlias, cast

from cobra import Model
from typing_extensions import TypedDict, overload

from VmaxBuilder.utils.file_handling import load_existing_file_based_on_extension

if TYPE_CHECKING:
    from VmaxBuilder.base.config_enum import MODEL_IMPLEMENTATIONS
from typing import Protocol

from VmaxBuilder.base.enums import PrimaryOutputFormat
from VmaxBuilder.base.exceptions import ConfigurationError


class Validator(Protocol):
    def __call__(self, value: Any) -> tuple[bool, str]: ...


@dataclass(frozen=True)
class StageLoadingInfo:
    stage_name: str
    directories: list[Path | str] | Path | str = field(default_factory=list)
    file_paths: dict[str, Path | str] = field(default_factory=dict)

    # def update(
    #     self,
    #     previous_object: "StageLoadingInfo",
    # ):
    #     if self.stage_name != previous_object.stage_name:
    #         raise ConfigurationError(
    #             f"Cannot update StageLoadingInfo for stage '{self.stage_name}' "
    #             f"with information from stage '{previous_object.stage_name}'."
    #         )
    #     ### directories
    #     if isinstance(previous_object.directories, (Path, str)):
    #         previous_object.directories = [previous_object.directories]
    #     if isinstance(self.directories, (Path, str)):
    #         self.directories = [self.directories]
    #
    #     updated_directories = (
    #         self.directories
    #         if self.directories is not None
    #         else previous_object.directories
    #     )


@dataclass(frozen=True)
class Stages:
    model_implementation: "MODEL_IMPLEMENTATIONS"
    model_loading_info: StageLoadingInfo
    # allocation_stage: str
    # protein_stage: str


@dataclass
class ImplementationConfig:
    pass


@dataclass
class Paths:
    base_dir: Path = field(repr=False)

    def __post_init__(self):
        self._rebuild(self.base_dir)

    def _rebuild(self, path: Path):
        path = Path(path).expanduser().resolve()

        self.results_dir = path
        self.diagnostics_dir = path / "diagnostics"
        self.artifacts_dir = path / "artifacts"
        self.metadata_dir = path / "metadata"
        self.outputs_dir = path / "outputs"

    def _create_dirs(self):
        for directory in [
            self.results_dir,
            self.diagnostics_dir,
            self.artifacts_dir,
            self.metadata_dir,
            self.outputs_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)


@dataclass(init=False)
class RunConfig:
    """
    Todo: make all parameters a specific class that returns its value, but contains
    documentation that can be called but isn't present. Type should be just the return type
    value (boo, str, int, etc). This way we can have a config class that is self-documenting
    and can be used to generate a config file with all the parameters and their documentation.
    """

    output_dir: Path
    run_name: str  # The results will be saved in a directory by this name in
    # the output_dir. If create_dynamically_named_results is True,
    # the run_name will be created from the final directory of each
    # stage's input directory, joined by underscores.

    # If False, the run_name will be used as is.
    create_dynamically_named_results: bool
    active_stages: list[str] | str
    primary_output_format: PrimaryOutputFormat
    write_additional_csv: bool
    run_input_validation: bool
    run_output_validation: bool
    run_diagnostics: bool
    print_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    lazy_load: bool
    lazy_validate: bool

    _output_dir: Path
    _run_name: str
    _print_level: str
    _ignore_fields: ClassVar[tuple[str, ...]] = (
        "_output_dir",
        "_run_name",
        "_print_level",
    )

    def __init__(
        self,
        output_dir: Path | None = None,
        run_name: str = "VmaxResults",
        create_dynamically_named_results: bool = False,
        active_stages: list[str] | str = "all",
        primary_output_format: PrimaryOutputFormat = PrimaryOutputFormat.FEATHER,
        write_additional_csv: bool = False,
        run_input_validation: bool = True,
        run_output_validation: bool = True,
        run_diagnostics: bool = True,
        print_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO",
        lazy_load: bool = False,
        lazy_validate: bool = False,
    ):
        self._initialized = False

        # Dit roept direct je setters aan!
        if output_dir is None:
            output_dir = Path.cwd() / "data/results/"
        self.output_dir = output_dir
        self.run_name = run_name

        self.create_dynamically_named_results = create_dynamically_named_results
        self.active_stages = active_stages
        self.primary_output_format = primary_output_format
        self.write_additional_csv = write_additional_csv
        self.run_input_validation = run_input_validation
        self.run_output_validation = run_output_validation
        self.run_diagnostics = run_diagnostics
        self.lazy_load = lazy_load
        self.lazy_validate = lazy_validate
        self._print_level = print_level

        results_dir = self._output_dir / self._run_name
        self.paths = Paths(results_dir)
        self._initialized = True

    def _sync_paths(self):
        results_dir = self._output_dir / self._run_name
        self.paths._rebuild(results_dir)

    @property
    def print_level(self) -> str:  # noqa
        return self._print_level

    @print_level.setter
    def print_level(self, _: str):
        if not getattr(self, "_initialized", False):
            self._print_level = self.print_level
        else:
            raise AttributeError(
                "print_level is read-only. Use the 'set_print_level' method of the "
                "Orchestrator class to change it."
            )

    @property
    def output_dir(self) -> Path:  # noqa
        return self._output_dir

    @output_dir.setter
    def output_dir(self, value: Path) -> None:
        self._output_dir = Path(value).expanduser().resolve()
        if getattr(self, "_initialized", False):
            self._sync_paths()

    @property
    def run_name(self) -> str:  # noqa
        return self._run_name

    @run_name.setter
    def run_name(self, value: str) -> None:
        self._run_name = value
        if getattr(self, "_initialized", False):
            self._sync_paths()


@dataclass
class PathInfo:
    stage_name: str
    directories: list[Path] = field(default_factory=list)
    file_paths: dict[str, Path] = field(default_factory=dict)

    def __repr__(self):
        return (
            f"PathInfo(stage_name={self.stage_name}, "
            f"directories={self.directories},"
            f"file_paths={self.file_paths})"
        )


@dataclass
class DiscoveredInput:
    input_name: str
    file_path: Path | None

    exists: bool

    source: Literal[
        "explicit_file_path",
        "directory_search",
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
    loader: Callable | None = load_existing_file_based_on_extension  # file → object loader
    loader_args: dict[str, Any] | None = None  # additional args for loader
    file_path: str | None = None  # file key for loading from files
    prefix: str | None = None  # file key for loading from files
    extensions: Iterable[str] | None = None  # allowed file extensions for loading
    validator: Validator | None = None  # function to validate the input


@dataclass(frozen=True)
class OutputSpec:
    name: str
    data_type: type | None = None
    scaffold_location: str | list[str] = "outputs"  # if files that are only outputs are
    # should remain in outputs, if also used as inputs, a copy is
    # placed in inputs.
    validator: Validator | None = None  # function to validate the output


@dataclass
class Scaffold:
    """Generated: validation needed.

    Description:
        Shared pipeline scaffold passed between stages.

    Args:
        inputs (dict[str, Any]): Input artifact bag.
        artifacts (dict[str, Any]): Intermediate artifacts.
        outputs (dict[str, Any]): Final stage outputs.
        metadata (dict[str, Any]): Reproducibility metadata.
        diagnostics (dict[str, Any]): Diagnostics payload.
        extras (dict[str, Any]): Extension bag for custom modules.
        loading_info (dict[str, StageLoadingInfo]): Per stage loading info
    """

    inputs: dict[str, Any]
    artifacts: dict[str, Any]
    outputs: dict[str, Any]
    metadata: dict[str, Any]
    diagnostics: dict[str, Any]
    extras: dict[str, Any]
    discovered_inputs: dict[str, dict[str, DiscoveredInput]] = field(default_factory=dict)

    def get_scaffold_location(self, key: str) -> str | None:
        """
        searches the scaffold for the given key in the following order:
        1. inputs
        2. outputs
        3. extras
        4. artifacts
        5. metadata
        6. diagnostics
        Does NOT search in loading info
        """
        sections = ["inputs", "outputs", "extras", "artifacts", "metadata", "diagnostics"]
        for section in sections:
            if key in getattr(self, section):
                return section

        return None

    def update_scaffold(self, new_scaffold_objects) -> None:
        """
        Updates the scaffold with the given key-value pair in the specified section.
        If the section does not exist, it will be created.
        """
        for key, value in new_scaffold_objects.items():
            location = self.get_scaffold_location(key)  # Ensure the scaffold location exists
            if location is None:
                self.outputs[key] = value  # Add new output if location doesn't exist
            else:
                getattr(self, location)[key] = (
                    value  # Update existing output if location exists
                )
