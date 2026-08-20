import json
import sys
from collections.abc import Iterator
from dataclasses import fields, is_dataclass
from pathlib import Path
from pprint import pprint
from typing import Any, TypeVar, cast, get_type_hints

import pandas as pd

from VmaxBuilder.base.classes import BaseImplementation, _iter_implementations
from VmaxBuilder.base.configs import (
    DiscoveredInput,
    FullConfig,
    ImplementationConfig,
    InputSpec,
    OutputSpec,
    PathInfo,
    RunConfig,
    Scaffold,
    StageLoading,
    StageLoadingInfo,
    TranscriptProcessingConfig,
)
from VmaxBuilder.stages.allocation.allocation import AllocationStage
from VmaxBuilder.stages.allocation.FairAllocation.implementation import (
    FairAllocationImplementation,
)
from VmaxBuilder.stages.Kcat.Kcat import KcatStage
from VmaxBuilder.stages.Kcat.UniKPMainSubstrate.implementation import (
    UniKPMainSubstrateImplementation,
)
from VmaxBuilder.stages.model.default.implementation import (
    DefaultIrreversibleModelImplementation,
)
from VmaxBuilder.stages.model.model import ModelStage
from VmaxBuilder.stages.protein.MvalueTrimmingExpressionPTR.implementation import (
    MvalueTrimmingExpressionPTRImplementation,
)
from VmaxBuilder.stages.protein.protein import ProteinStage
from VmaxBuilder.stages.Vmax.default.reaction_resolving import (
    DefaultVmaxReactionResolving,
)
from VmaxBuilder.stages.Vmax.Vmax import VmaxStage
from VmaxBuilder.utils.custom_logging import CustomLogger, custom_asdict
from VmaxBuilder.utils.iterables import make_json_serializable

run_config_type_hints = get_type_hints(RunConfig)
PrintLevelType = run_config_type_hints.get("print_level", str)

"""
Users can provide one or more directories for a specific stage, in which all inputspes
with their denoted extension and file keys will be sought. Alternatively users
can provide a dictionary with file_paths for each input spec of a specific stage.

add check if at least one dir or path is provided
then search based on inputs if not found we raise error

"""
ImplT = TypeVar("ImplT", bound=BaseImplementation[Any])
pd.set_option(
    "future.no_silent_downcasting", True
)  # to avoid future warning for downcasting in pandas

# todo: add validator at end of implementation to see if all things in outputs
# are now present in scaffold outputs


class Orchestrator:
    stages = {
        "model": ModelStage,
        "protein": ProteinStage,
        "allocation": AllocationStage,
        "Kcat": KcatStage,
        "Vmax": VmaxStage,
    }

    ImplT = TypeVar("ImplT", bound=BaseImplementation[Any])

    def __init__(self, stage_implementations: StageLoading, run_config: RunConfig):
        # base initialization
        self.logger = CustomLogger(
            "Orchestrator",
        )
        self.set_print_level(run_config.print_level)
        self.discovered_inputs: dict[str, dict[str, DiscoveredInput]] = {
            stage: {} for stage in self.stages
        }
        self.config = self._build_default_config(run_config=run_config)
        self.scaffold = self._initialise_scaffold()

        # get user input for loading and implementations
        self.loading_info = {
            stage: getattr(stage_implementations, f"{stage}_loading_info")
            for stage in self.stages
        }
        # self._resolve_stage_implementations()
        # self.scaffold.discovered_inputs = self.discovered_inputs
        self._attempted_discovered_inputs: dict[str, InputSpec] = {}
        self._validated_inputs: dict[str, InputSpec] = {}
        self._validated_outputs: dict[str, OutputSpec] = {}
        self.validation_results: dict[str, Any] = {}
        self.diagnostics: dict[str, Any] = {}
        self._all_loggers = [self.logger]

    def set_model_implementation(self, implementation_cls: type[ImplT]) -> ImplT:
        implementation = implementation_cls(full_config=self.config)
        self._model = implementation
        self.config.model = implementation.config
        self.model_stage = self.stages["model"](
            implementation=implementation, full_config=self.config
        )
        self.set_print_level(self.config.run.print_level)
        self._discover_user_submitted_paths(stage_name="model")
        self.scaffold.discovered_inputs = self.discovered_inputs

        return implementation

    def set_protein_implementation(self, implementation_cls: type[ImplT]) -> ImplT:
        implementation = implementation_cls(full_config=self.config)
        # todo: make sure that stage is correct and we cant use
        # incorrect stage implementation for protein stage
        self._protein = implementation
        self.config.protein = implementation.config
        print("protein config: ", self.config.protein)
        self.protein_stage = self.stages["protein"](
            implementation=implementation, full_config=self.config
        )
        self.set_print_level(self.config.run.print_level)
        self._discover_user_submitted_paths(stage_name="protein")
        self.scaffold.discovered_inputs = self.discovered_inputs

        return implementation

    def set_allocation_implementation(self, implementation_cls: type[ImplT]) -> ImplT:
        implementation = implementation_cls(full_config=self.config)
        self._allocation = implementation
        self.config.allocation = implementation.config
        self.allocation_stage = self.stages["allocation"](
            implementation=implementation, full_config=self.config
        )
        self.set_print_level(self.config.run.print_level)
        self._discover_user_submitted_paths(stage_name="allocation")
        self.scaffold.discovered_inputs = self.discovered_inputs

        return implementation

    def set_Kcat_implementation(self, implementation_cls: type[ImplT]) -> ImplT:
        implementation = implementation_cls(full_config=self.config)
        self._Kcat = implementation
        self.config.Kcat = implementation.config
        self.Kcat_stage = self.stages["Kcat"](
            implementation=implementation, full_config=self.config
        )
        self.set_print_level(self.config.run.print_level)
        self._discover_user_submitted_paths(stage_name="Kcat")
        self.scaffold.discovered_inputs = self.discovered_inputs

        return implementation

    def set_Vmax_implementation(self, implementation_cls: type[ImplT]) -> ImplT:
        implementation = implementation_cls(full_config=self.config)
        self._Vmax = implementation
        self.config.Vmax = implementation.config
        self.Vmax_stage = self.stages["Vmax"](
            implementation=implementation, full_config=self.config
        )
        self.set_print_level(self.config.run.print_level)
        self._discover_user_submitted_paths(stage_name="Vmax")
        self.scaffold.discovered_inputs = self.discovered_inputs

        return implementation

    def _save_metadata(self, metadata: dict[str, Any]):
        metadata_path = self.config.run.paths.metadata_dir / "orchestrator_metadata.json"
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Metadata saved to {metadata_path}")
        with open(metadata_path, "w") as f:
            json.dump(make_json_serializable(metadata), f, indent=4)

    def run(self):
        self._discover_user_submitted_paths()
        self.config.run.paths._create_dirs()
        self.logger.info("Starting orchestrator run...")
        metadata = self.create_metadata()
        self._save_metadata(metadata)
        self._discover_optional_dependencies()

        if not self.config.run.lazy_load:
            self.load_inputs()
            if not self.config.run.lazy_validate:
                self.validate_loaded_inputs()

        for stage_name in self.stages:
            self.logger.info(f"Running stage: {stage_name}")
            self._run_stage(stage_name)

        self.logger.info("Orchestrator run completed.")

    def _discover_optional_dependencies(self):
        # this function simply checks the currently enabled implementations and
        # sees if any has the class attribute OPTIONAL_DEPENDENCIES and
        # if so, calls its function before any other code is ran.
        # For instance, UniKP requires several models to be downloaded,
        # as well as --submodule recursive to be used to get the fork
        # of the UniKP repo. As this breaks the normal flow of the orchestrator,
        # we first let users know. The function called by OPTIONAL_DEPENDENCIES
        # is an installation function that checks if the dependencies are present
        # if not, asks for y/n input to download them.
        # Afterwards the orchestrator should be called again as new python
        # files are now discoverable (think of this as uv installing packages)

        installed_one_or_more_dependencies = False
        for stage_name in self.stages:
            stage = getattr(self, f"{stage_name}_stage", None)
            if stage is not None:
                stage_implementation: BaseImplementation = stage.implementation
                for implementation in _iter_implementations(stage_implementation):
                    if isinstance(implementation, type):
                        continue
                    optional_dependencies = getattr(
                        implementation, "OPTIONAL_DEPENDENCIES", None
                    )
                    if optional_dependencies is not None:
                        self.logger.info(
                            f"Checking optional dependencies for "
                            f"{implementation.__class__.__name__}..."
                        )
                        for dependency in optional_dependencies:
                            installed_something = dependency()()
                            if installed_something:
                                installed_one_or_more_dependencies = True
        if installed_one_or_more_dependencies:
            self.logger.attention(
                (
                    "One or more optional dependencies were installed. "
                    "Please rerun the orchestrator to ensure all dependencies are loaded."
                ),
                print_level=1,
            )
            # exit the program
            sys.exit(0)

    def return_config(
        self, sections: list[str] | str | None = None, verbose: bool = True
    ) -> dict[str, dict[str, Any]]:
        return_dict: dict[str, dict[str, Any]] = {}
        if not hasattr(self.config, "run") or self.config.run is None:
            raise ValueError(
                "Config must have a 'run' section with a valid RunConfig instance."
            )
        if (sections is not None) and not isinstance(sections, (str, list)):
            raise ValueError("Sections must be None, a string, or a list of strings.")

        elif sections is None or sections == "all":
            pprint(custom_asdict(self.config, verbose=verbose))
            return_dict = custom_asdict(self.config, verbose=verbose)
        elif isinstance(sections, str):
            pprint(custom_asdict(getattr(self.config, sections), verbose=verbose))
            return_dict[sections] = custom_asdict(
                getattr(self.config, sections), verbose=verbose
            )
        elif isinstance(sections, list):
            for section in sections:
                if not hasattr(self.config, section):
                    raise ValueError(f"Section '{section}' not found in config.")
                allowed_types = tuple(f.type for f in fields(self.config))
                if not isinstance(getattr(self.config, section), allowed_types):
                    raise ValueError(f"Section '{section}' is not a valid config section.")
                pprint(custom_asdict(getattr(self.config, section), verbose=verbose))
                return_dict[section] = custom_asdict(
                    getattr(self.config, section), verbose=verbose
                )
        return return_dict

    def create_metadata(self) -> dict[str, Any]:
        discovered_paths = self.return_discovered_paths()
        discovered_paths_serializable = {
            key: {input_name: discovered_input.to_dict()}
            for key, value in discovered_paths.items()
            for input_name, discovered_input in value.items()
        }

        metadata = {
            "orchestrator": {
                "implementation": type(self).__name__,
                "date_created": pd.Timestamp.now().isoformat(),
                "params": self.return_non_default_configs(),
                "paths": {
                    "user_submitted_paths": [
                        path_info.to_dict()
                        for path_info in self.return_user_submitted_paths()
                    ],
                    "discovered_paths": discovered_paths_serializable,
                },
            }
        }
        return metadata

    def return_non_default_configs(self) -> dict[str, dict[str, Any]]:
        non_default_configs = {}

        for subconfig_name in self.config.__dataclass_fields__:
            subconfig = getattr(self.config, subconfig_name)

            if not is_dataclass(subconfig):
                continue

            # Create pristine default instance
            if subconfig_name == "paths":
                continue
            else:
                default_subconfig = type(subconfig)()

            non_default_fields = {}
            ignored_fields = getattr(subconfig, "_ignore_fields", set())

            for field_info in fields(subconfig):
                if field_info.name in ignored_fields:
                    continue  # Skip ignored fields
                field_name = field_info.name

                current_value = getattr(subconfig, field_name)
                default_value = getattr(default_subconfig, field_name)

                if current_value != default_value:
                    non_default_fields[field_name] = {
                        "default": default_value,
                        "current": current_value,
                    }

            if non_default_fields:
                non_default_configs[subconfig_name] = non_default_fields
        pprint({"Non-default_arguments": non_default_configs})

        return non_default_configs

    def set_stage_loading_info(self, stage: str, loading_info: StageLoadingInfo):
        if stage not in self.stages:
            raise ValueError(f"Stage '{stage}' is not a valid stage.")
        self.loading_info[stage] = loading_info
        self._discover_user_submitted_paths(stage_name=stage)

    def _get_all_loggers(self) -> list[CustomLogger]:
        all_loggers = [self.logger]
        for stage_name in self.stages:
            stage = getattr(self, f"{stage_name}_stage", None)
            if stage is not None:
                all_loggers.append(stage.logger)
                stage_implementation: BaseImplementation = stage.implementation
                for implementation in _iter_implementations(stage_implementation):
                    if isinstance(implementation, type):
                        continue
                    all_loggers.append(implementation.logger)
                    if hasattr(implementation, "diagnostics"):
                        for diagnostic_impl in implementation.diagnostics:
                            all_loggers.append(diagnostic_impl.logger)

                additional_implementations = getattr(stage, "additional_implementations", {})
                for additional_implementation_cls in additional_implementations.values():
                    for additional_implementation in _iter_implementations(
                        additional_implementation_cls
                    ):
                        if isinstance(additional_implementation, type):
                            continue
                        all_loggers.append(additional_implementation.logger)
        print("All loggers in the orchestrator:")
        pprint([logger.name for logger in all_loggers])
        return all_loggers

    def set_print_level(self, level: str | int, log_modification: bool = True):
        mapping = {
            "DEBUG": 4,
            "INFO": 3,
            "WARNING": 2,
            "ERROR": 1,
            "CRITICAL": 0,
        }
        reverse_mapping = {v: k for k, v in mapping.items()}
        if isinstance(level, str):
            if level.upper() not in mapping:
                raise ValueError(f"Invalid print level: {level}")
            level_int = mapping[level.upper()]
            level_literal = level.upper()

        elif isinstance(level, int):
            if level not in mapping.values():
                raise ValueError(f"Invalid print level: {level}")
            level_int = level
            level_literal = reverse_mapping[level]
        else:
            raise ValueError(f"Print level must be a string or integer, got {type(level)}")

        all_loggers = self._get_all_loggers()

        for logger in all_loggers:
            logger.set_print_level(level_int)
        # self.logger.set_print_level(level_int)

        if log_modification:
            self.logger.info(
                f"Print level adjusted to {level_literal} "
                "in the following loggers:"
                f"{[logger.name for logger in all_loggers]}",
                print_level=1,
            )
        if hasattr(self, "config"):
            # necessary to init using the caster
            # self.config.run._print_level = cast(PrintLevelType, level_literal)
            self.config.run.print_level = cast(PrintLevelType, level_literal)

        self._all_loggers = all_loggers

    def return_user_submitted_paths(self) -> list[PathInfo]:
        user_submitted_paths = []
        for stage_name in self.stages:
            loading_info = self.loading_info.get(stage_name)
            if loading_info:
                user_submitted_paths.append(
                    PathInfo(
                        stage_name=stage_name,
                        directories=loading_info.directories,
                        file_paths=loading_info.file_paths,
                    )
                )
        self.logger.info("User submitted paths:")
        pprint(custom_asdict(user_submitted_paths))

        return user_submitted_paths

    def load_inputs(self) -> None:
        for stage_name in self.stages:
            stage = getattr(self, f"{stage_name}_stage")
            stage_implementation: BaseImplementation = stage.implementation
            for implementation in _iter_implementations(stage_implementation):
                if isinstance(implementation, type):
                    continue
                implementation.load_inputs(scaffold=self.scaffold)

    def validate_loaded_inputs(self):
        """
        Validates inputs after loading using the InputSpecs validation function.
        Note that his does not
        """
        for stage_name in self.stages:
            stage = getattr(self, f"{stage_name}_stage")
            stage_implementation: BaseImplementation = stage.implementation
            if not self.validation_results.get(stage_name, False):
                self.validation_results[stage_name] = {}
            for implementation in _iter_implementations(stage_implementation):
                if isinstance(implementation, type):
                    continue
                self.scaffold, validation_results = implementation.validate_inputs(
                    already_validated_inputs=self._validated_inputs,
                    scaffold=self.scaffold,
                )
                self.validation_results[stage_name].update(validation_results)

    def _run_stage(self, stage_name: str):
        # todo: consider whether should be public or private (orchestration run is sequential)
        stage = getattr(self, f"{stage_name}_stage")
        self.scaffold = stage.run(self.scaffold)

    @staticmethod
    def _initialise_scaffold(scaffold: Scaffold | None = None) -> Scaffold:
        if scaffold is None:
            return Scaffold(
                inputs={},
                artifacts={},
                outputs={},
                metadata={},
                diagnostics={},
                extras={},
                discovered_inputs={},
            )
        else:
            raise ValueError("Scaffold must be None or a valid Scaffold instance.")

    def walk_implementation_dag(self) -> list[tuple[str, str]]:
        """
        This function walks through each implementation and its child implementations,
        and checks, in order, what the state and return state of different implementations
        are. This also deals with optional inputs that lead to a decision tree (if present
        don't run the extra code, otherwise do run it). It assumes that files are either
        created at some point earlier and thus present, or are denoted loadable and thus
        can be loaded. It does not check whether files are actually present on those locations
        nor whether they are valid."""
        pass
        dag: list[tuple[str, str]] = []
        return dag

    def validate_virtual_inputs_outputs(self):
        """
        Only checks the mermaid plot created to ensure that the full orchestration
        implementation is valid and that no implementation requires any inputs that
        are not provided or loaded by other implementations. Specifically ensures that
        optional inputs (for instance Ensembl data) are created if they were not present.
        """
        pass

    def _build_default_config(self, run_config: RunConfig) -> FullConfig:
        return FullConfig(
            model=ImplementationConfig(),
            protein=ImplementationConfig(),
            allocation=ImplementationConfig(),
            Kcat=ImplementationConfig(),
            Vmax=ImplementationConfig(),
            run=run_config,
            paths=run_config.paths,
            transcripts=TranscriptProcessingConfig(),
        )

    def return_discovered_paths(self) -> dict[str, dict[str, DiscoveredInput]]:
        self.logger.info("Discovered paths:")
        pprint(custom_asdict(self.discovered_inputs))
        return self.discovered_inputs

    def _discover_in_main_implementations(self, stage_name: str):
        main_implementation = getattr(self, f"{stage_name}_stage").implementation
        for implementation in _iter_implementations(main_implementation):
            for input_spec in implementation.INPUTS:
                discovered_input = self._discover_input(
                    input_spec=input_spec,
                    loading_info=self.loading_info[stage_name],
                )
                if discovered_input is not None:
                    self.discovered_inputs[stage_name][input_spec.name] = discovered_input
                    self.logger.valid(
                        f"Discovered input '{input_spec.name}' for stage '{stage_name}': "
                        f"{discovered_input.file_path}"
                        f"(source: {discovered_input.source})"
                    )
                else:
                    if input_spec.name in self._attempted_discovered_inputs:
                        continue
                    self._attempted_discovered_inputs[input_spec.name] = input_spec
                    self.logger.warning(
                        f"Input '{input_spec.name}' for stage '{stage_name}' "
                        "could not be discovered."
                    )

    def _discover_in_additional_implementations(self, stage_name: str):
        additional_implementation_cls = getattr(
            getattr(self, f"{stage_name}_stage"), "additional_implementations", {}
        )

        if not additional_implementation_cls:
            return

        for additional_implementation in additional_implementation_cls.values():
            for input_spec in additional_implementation.INPUTS:
                discovered_input = self._discover_input(
                    input_spec=input_spec,
                    loading_info=self.loading_info[stage_name],
                )
                if discovered_input is not None:
                    self.discovered_inputs[stage_name][input_spec.name] = discovered_input
                    self.logger.valid(
                        f"Discovered input '{input_spec.name}' for stage '{stage_name}': "
                        f"{discovered_input.file_path}"
                        f"(source: {discovered_input.source})"
                    )
                else:
                    if input_spec.name in self._attempted_discovered_inputs:
                        continue
                    self._attempted_discovered_inputs[input_spec.name] = input_spec
                    self.logger.warning(
                        f"Input '{input_spec.name}' for stage '{stage_name}' "
                        "could not be discovered."
                    )

    def _discover_user_submitted_paths(self, stage_name: str | None = None):
        if stage_name is not None:
            self.discovered_inputs[stage_name] = {}
            stages = [stage_name]
        else:
            self.discovered_inputs: dict[str, dict[str, DiscoveredInput]] = {
                stage: {} for stage in self.stages
            }
            stages = self.stages
        for stage_name in stages:
            if self.loading_info.get(stage_name) is None:
                self.logger.warning(
                    f"No loading info provided for stage '{stage_name}'. "
                    "Skipping input discovery for this stage."
                )
                continue

            self._discover_in_main_implementations(stage_name)
            self._discover_in_additional_implementations(stage_name)

    def _discover_input(self, input_spec, loading_info) -> DiscoveredInput | None:
        explicit_path = None
        if input_spec.loader and input_spec.file_path:
            explicit_path = self._resolve_explicit_file_path(
                input_spec,
                loading_info,
            )

        if explicit_path is not None:
            return DiscoveredInput(
                input_name=input_spec.name,
                file_path=explicit_path,
                exists=True,
                source="explicit_file_path",
                warning=None,
            )

        search_result = self._search_directories(
            input_spec,
            loading_info,
        )
        if search_result is not None:
            return DiscoveredInput(
                input_name=input_spec.name,
                file_path=search_result,
                exists=True,
                source="directory_search",
                warning=None,
            )
        return None

    def _resolve_explicit_file_path(
        self,
        input_spec: InputSpec,
        loading_info: StageLoadingInfo,
    ) -> Path | None:
        file_paths = loading_info.file_paths or {}

        if input_spec.name not in file_paths:
            return None

        path = Path(file_paths[input_spec.name]).expanduser().resolve()

        if not path.exists():
            self.logger.warning(f"File not found for '{input_spec.name}': {path}")
            return None

        return path

    def _normalize_directories(
        self,
        directories,
    ) -> list[Path]:
        if directories is None:
            return []

        if isinstance(directories, (str, Path)):
            directories = [directories]

        return [Path(d).expanduser().resolve() for d in directories]

    def _search_directories(
        self,
        input_spec: InputSpec,
        loading_info: StageLoadingInfo,
    ) -> Path | None:
        matches = []
        self.logger.info(f"Searching directories for '{input_spec.name}'.")
        self.logger.debug(f"Directories to search: {loading_info.directories}")

        for directory in self._normalize_directories(loading_info.directories):
            if not directory.exists():
                self.logger.warning(f"Directory not found: {directory}")
                continue

            matches.extend(
                self._find_matching_files(
                    directory,
                    input_spec,
                )
            )

        return self._select_match(
            matches,
            input_spec,
        )

    def _find_matching_files(
        self,
        directory: Path,
        input_spec: InputSpec,
    ) -> list[Path]:
        matches = []
        if input_spec.prefix is None or input_spec.extensions is None:
            return matches

        for extension in input_spec.extensions:
            matches.extend(directory.glob(f"{input_spec.prefix}*{extension}"))

        return matches

    def _select_match(
        self,
        matches: list[Path],
        input_spec: InputSpec,
    ) -> Path | None:
        if len(matches) == 0:
            self.logger.debug(f"No file found for '{input_spec.name}'.")
            return None

        if len(matches) > 1:
            # Sort matches by extension priority if provided.
            if input_spec.extensions:
                extension_order = {ext: i for i, ext in enumerate(input_spec.extensions)}
                matches.sort(key=lambda x: extension_order.get(x.suffix, float("inf")))
                self.logger.warning(
                    f"Multiple files found for '{input_spec.name}'. "
                    "Sorting by extension priority and using first match."
                )
            else:
                self.logger.warning(
                    f"Multiple files found for '{input_spec.name}'. "
                    "No extension priority configured; using first match."
                )
            self.logger.warning(
                f"Candidate matches for '{input_spec.name}': {matches}. "
                f"Selected: {matches[0]}"
            )

        return matches[0]


if __name__ == "__main__":
    base_dir = Path("~/git/SWAPAM/data/for_SWAMP/")
    models_dir = base_dir / "models"
    model_name = "Human-GEM-2.0.0"
    model_dir = models_dir / model_name
    model_path = model_dir

    expression_name = "NCI_60_human"
    expression_path = base_dir / "expression_datasets" / expression_name
    Kcat_path = base_dir / "Kcat_predictions" / "UniKPV1" / "model_inhouse_v7_human"
    ptr_path = base_dir / "PTR_datasets" / "Eraslan2019_human"
    # proteomics_path = base_dir / "proteomics" / "NCI60"
    output_path = Path("~/git/VmaxBuilder/data/run_example_output")
    create_dynamically_named_results = False
    model_stage_loading_info = StageLoadingInfo(
        stage_name="model",
        directories=model_dir,
        file_paths={
            "smiles_df": model_dir / "SMILES_df.csv",
            "transcript_df": model_dir / "transcript_df.csv",
        },
    )
    protein_stage_loading_info = StageLoadingInfo(
        stage_name="protein",
        directories=[
            expression_path,
            ptr_path,
        ],
    )

    allocation_stage_loading_info = StageLoadingInfo(
        stage_name="allocation",
    )
    kcat_stage_loading_info = StageLoadingInfo(
        stage_name="Kcat",
        directories=[Kcat_path],
    )
    Vmax_stage_loading_info = StageLoadingInfo(
        stage_name="Vmax",
    )
    # Protein inputs (set whichever mode needs).
    stage_loading_info = StageLoading(
        model_loading_info=model_stage_loading_info,
        protein_loading_info=protein_stage_loading_info,
        allocation_loading_info=allocation_stage_loading_info,
        Kcat_loading_info=kcat_stage_loading_info,
        Vmax_loading_info=Vmax_stage_loading_info,
    )

    run_config = RunConfig(
        output_dir=output_path,
        run_name=f"{expression_name}_run",
        create_dynamically_named_results=create_dynamically_named_results,
        # print_level="DEBUG",
    )

    orchestrator = Orchestrator(stage_loading_info, run_config)
    orchestrator.set_print_level("WARNING")
    model = orchestrator.set_model_implementation(DefaultIrreversibleModelImplementation)
    protein = orchestrator.set_protein_implementation(
        MvalueTrimmingExpressionPTRImplementation
    )
    allocation = orchestrator.set_allocation_implementation(FairAllocationImplementation)
    Kcat = orchestrator.set_Kcat_implementation(UniKPMainSubstrateImplementation)
    Vmax = orchestrator.set_Vmax_implementation(DefaultVmaxReactionResolving)

    protein.config.expression_sample_type_map = {idx: "heart" for idx in range(1, 1000)}

    protein.config.PTR_special_gene_groups = {"transport_reactions": []}
    # todo: rename use_special_groups_for_unobserved_imputation to PTR

    protein.config.use_special_groups_for_unobserved_imputation = True

    # # model.config.maximum_transcript_ifp_expansion_2 = 800
    # orchestrator.config.model.maximum_transcript_ifp_expansion = 800
    #
    # print(
    #     "\nshowing scaffold user submitted paths: ",
    #     orchestrator.scaffold.discovered_inputs,
    # )
    # print("showing discovered paths: ", orchestrator.return_discovered_paths())
    # print("Initial config:")
    #
    orchestrator.return_config(verbose=False)
    # print("setting print level to DEBUG...")
    orchestrator.config.run.overwrite_existing_results = True
    # print("showing user submitted  paths:")
    # orchestrator.return_user_submitted_paths()
    #
    # print("setting new  user submitted paths...")
    # orchestrator.set_stage_loading_info(
    #     "model",
    #     StageLoadingInfo(
    #         stage_name="model",
    #         directories=model_dir,
    #         file_paths={
    #             "smiles_df": model_dir / "final_SMILES_metabolite_df.csv",
    #             "transcript_df": model_dir / "final_transcript_df.csv",
    #         },
    #     ),
    # )
    # print("showing updated user submitted paths:")
    # orchestrator.return_user_submitted_paths()
    #
    # print("Loading inputs...")
    # orchestrator.load_inputs()
    # print(
    #     "showing scaffold user submitted paths: ",
    #     orchestrator.scaffold.discovered_inputs,
    # )
    # # orchestrator.config.run.lazy_validate = True
    # # orchestrator.config.model.make_copy = True
    orchestrator.logger.attention("Starting orchestrator run...")
    orchestrator.run()
