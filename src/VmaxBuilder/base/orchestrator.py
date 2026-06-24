import inspect
from collections.abc import Iterator
from dataclasses import (  # asdict,
    dataclass,
    field,
    fields,
    is_dataclass,
    make_dataclass,
)
from pathlib import Path
from pprint import pprint
from typing import Any, cast, get_type_hints

from VmaxBuilder.base.classes import BaseImplementation
from VmaxBuilder.base.config_enum import (
    ALLOCATION_IMPLEMENTATIONS,
    MODEL_IMPLEMENTATIONS,
    PROTEIN_IMPLEMENTATIONS,
    implementations,
)
from VmaxBuilder.base.configs import (
    DiscoveredInput,
    FullConfig,
    ImplementationConfig,
    InputSpec,
    PathInfo,
    RunConfig,
    Scaffold,
    StageLoadingInfo,
    Stages,
)
from VmaxBuilder.base.exceptions import ImplementationConfigConflictError
from VmaxBuilder.base.registry import IMPLEMENTATION_REGISTRY
from VmaxBuilder.stages.model.model import ModelStage
from VmaxBuilder.utils.custom_logging import CustomLogger

run_config_type_hints = get_type_hints(RunConfig)
PrintLevelType = run_config_type_hints.get("print_level", str)

"""
Users can provide one or more directories for a specific stage, in which all inputspes
with their denoted extension and file keys will be sought. Alternatively users
can provide a dictionary with file_paths for each input spec of a specific stage.

add check if at least one dir or path is provided
then search based on inputs if not found we raise error

"""


# todo: move to utils.py
def custom_asdict(obj):
    """ """
    if is_dataclass(obj):
        result = {}
        # Controleer of deze specifieke klasse velden wil negeren
        ignored = getattr(obj, "_ignore_fields", set())

        for f in fields(obj):
            if f.name in ignored:
                continue  # Sla dit veld volledig over

            value = getattr(obj, f.name)
            result[f.name] = custom_asdict(value)
        return result

    elif isinstance(obj, list):
        return [custom_asdict(v) for v in obj]
    elif isinstance(obj, dict):
        return {k: custom_asdict(v) for k, v in obj.items()}
    elif isinstance(obj, tuple):
        return tuple(custom_asdict(v) for v in obj)

    return obj


class Orchestrator:
    registry: dict[str, type[BaseImplementation]] = IMPLEMENTATION_REGISTRY
    stages = {
        "model": ModelStage,
        # "protein": ProteinStage,
        # "allocation": AllocationStage,
        # add more stages here as needed
        # "stage_name": StageClass,
    }

    def __init__(self, stage_implementations: Stages, run_config: RunConfig):
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
        self._resolve_stage_implementations(stage_implementations=stage_implementations)
        self.scaffold.discovered_inputs = self.discovered_inputs

    def run(self):
        self._discover_user_submitted_paths()
        self.logger.info("Starting orchestrator run...")
        if not self.config.run.lazy_load:
            self.load_inputs()
            if not self.config.run.lazy_validate:
                self.validate_loaded_inputs()

        for stage_name in self.stages:
            self.logger.info(f"Running stage: {stage_name}")
            self._run_stage(stage_name)

        self.logger.info("Orchestrator run completed.")

    def show_config(self, sections: list[str] | str | None = None):
        if not hasattr(self.config, "run") or self.config.run is None:
            raise ValueError(
                "Config must have a 'run' section witha valid RunConfig instance."
            )
        if (sections is not None) and not isinstance(sections, (str, list)):
            raise ValueError("Sections must be None, a string, or a list of strings.")

        elif sections is None or sections == "all":
            pprint(custom_asdict(self.config))
        elif isinstance(sections, str):
            pprint(custom_asdict(getattr(self.config, sections)))
        elif isinstance(sections, list):
            for section in sections:
                if not hasattr(self.config, section):
                    raise ValueError(f"Section '{section}' not found in config.")
                allowed_types = tuple(f.type for f in fields(self.config))
                if not isinstance(getattr(self.config, section), allowed_types):
                    raise ValueError(f"Section '{section}' is not a valid config section.")
                pprint(custom_asdict(getattr(self.config, section)))

    def set_stage_loading_info(self, stage: str, loading_info: StageLoadingInfo):
        if stage not in self.stages:
            raise ValueError(f"Stage '{stage}' is not a valid stage.")
        self.loading_info[stage] = loading_info
        self._discover_user_submitted_paths()

    def set_stage_implementation(
        self,
        stage: str,
        implementation_name: MODEL_IMPLEMENTATIONS
        | PROTEIN_IMPLEMENTATIONS
        | ALLOCATION_IMPLEMENTATIONS,
    ):
        if stage not in self.stages:
            raise ValueError(f"Stage '{stage}' is not a valid stage.")
        impl_cls = self._resolve_implementation(stage, implementation_name.value)
        implementation = impl_cls(full_config=self.config)
        flattened_config_cls = self._get_implementation_config_class(
            implementation=implementation
        )
        setattr(self.config, f"{stage}_config", flattened_config_cls())

        setattr(
            self,
            f"{stage}_stage",
            self.stages[stage](implementation=implementation, full_config=self.config),
        )

        self.logger.info(
            f"Set implementation for stage '{stage}' to '{implementation_name.value}'."
        )
        self._discover_user_submitted_paths()

    def set_print_level(self, level: str | int):
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

        self.logger.set_print_level(level_int)

        self.logger.info(f"Print level set to: {level_literal}")
        if hasattr(self, "config"):
            # necessary to init using the caster
            self.config.run._print_level = cast(PrintLevelType, level_literal)

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
            for implementation in self._iter_implementations(stage_implementation):
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
            for implementation in self._iter_implementations(stage_implementation):
                if isinstance(implementation, type):
                    continue
                self.scaffold, _ = implementation.validate_inputs(scaffold=self.scaffold)

    def _run_stage(self, stage_name: str):
        # todo: consider whether should be public or private (orchestration run is sequential)
        stage = getattr(self, f"{stage_name}_stage")
        self.scaffold = stage.run(self.scaffold)

    def _iter_implementations(
        self,
        implementation: type[BaseImplementation] | BaseImplementation,
    ) -> Iterator[BaseImplementation | type[BaseImplementation]]:
        yield implementation

        child_implementations: list[BaseImplementation] = getattr(
            implementation, "child_implementations", []
        )

        for child_implementation in child_implementations:
            yield from self._iter_implementations(child_implementation)

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

    def _resolve_stage_implementations(self, stage_implementations: Stages):
        for stage in self.stages:
            impl_name = getattr(stage_implementations, f"{stage}_implementation")
            self.set_stage_implementation(stage, impl_name)

    def walk_implementation_dag(self) -> list[tuple[str, str]]:
        """
        This function walks through each implementation and its child implementations,
        and checks, in order, what the state and return state of different implementations
        are. This also deals with optional inputs that lead to a decision tree (if present
        don't run the extra code, otherwise do run it). It assumes that files are either
        created at some point earlier and thus present, or are denoted loadable and thus
        can be loaded. It does not check whether files are actually present on those locations
        nor whether they are valid.
        """
        pass
        dag: list[tuple[str, str]] = []
        return dag

    def validate_virtual_inputs_outputs(self):
        """
        Only checks the mermaid plot created to ensure that the full orchestration
        implementation is valid and that no implementation requires any inputs that
        are not provided or loaded by other implementations. Specifically ensures that
        optional inputs (for isntance ensembl data) are created if they were not present.
        """
        pass

    def _resolve_implementation(self, stage: str, impl_name: str) -> type[BaseImplementation]:
        key = f"{stage}:{impl_name}"
        if key not in self.registry:
            raise ValueError(f"Implementation '{impl_name}' for stage '{stage}' not found.")
        return self.registry[key]

    def _get_implementation_config_class(
        self,
        *,
        implementation: BaseImplementation | type[BaseImplementation] | None = None,
        stage: str | None = None,
        impl_name: str | None = None,
    ) -> type:
        if implementation is not None:
            if not isinstance(implementation, (BaseImplementation, type)):
                raise TypeError(
                    "The 'implementation' argument must be an "
                    "instance or class of BaseImplementation."
                )
            implementation = implementation

        elif stage is None or impl_name is None:
            raise ValueError(
                "Either 'implementation' or both 'stage' and 'impl_name' must be provided."
            )
        else:
            implementation = self._resolve_implementation(stage, impl_name)
        stage_configs = self._collect_implementation_configs(implementation)
        self._validate_config_conflicts(stage_configs)
        flattened_stage_config = self._build_flattened_config(stage_configs)

        return flattened_stage_config

    def _collect_implementation_configs(
        self,
        implementation: type[BaseImplementation] | BaseImplementation,
    ) -> list[type]:
        configs = []

        for impl in self._iter_implementations(implementation):
            config_cls = getattr(impl, "CONFIG_CLASS", None)
            if config_cls is not None:
                configs.append(config_cls)

        return configs

    def _validate_config_conflicts(
        self,
        config_classes: list[type],
    ):
        key_owners = {}
        for config_cls in config_classes:
            source_file = inspect.getfile(config_cls)
            _, line_number = inspect.getsourcelines(config_cls)
            if not is_dataclass(config_cls):
                raise TypeError(
                    f"Config class '{config_cls.__name__}' "
                    f"in {source_file} is not a dataclass."
                )

            for _field in fields(config_cls):
                if _field.name in key_owners:
                    previous = key_owners[_field.name]
                    if not isinstance(previous["config"], type) or not isinstance(
                        config_cls, type
                    ):
                        raise ValueError(
                            f"Conflict detected for config key '{_field.name}' between "
                            f"{previous['config']} and {config_cls},"
                            "but one of them is not a class."
                        )

                    raise ImplementationConfigConflictError(
                        key=_field.name,
                        config_a=previous["config"],
                        config_b=config_cls,
                        file_a=f"{previous['file']}:{previous['line']}",
                        file_b=f"{source_file}:{line_number}",
                    )

                key_owners[_field.name] = {
                    "config": config_cls,
                    "file": source_file,
                    "line": line_number,
                }

    def _build_default_config(self, run_config: RunConfig) -> FullConfig:
        return FullConfig(
            model=ImplementationConfig(), run=run_config, paths=run_config.paths
        )

    def _build_flattened_config(self, config_classes: list[type]) -> type:
        combined_fields = []

        for config_cls in config_classes:
            for _field in fields(config_cls):
                combined_fields.append(
                    (
                        _field.name,
                        _field.type,
                        _field,
                    )
                )

        return make_dataclass(
            cls_name="CombinedConfig",
            fields=combined_fields,
            bases=(ImplementationConfig,),
        )

    def return_discovered_paths(self) -> dict[str, dict[str, DiscoveredInput]]:
        self.logger.info("Discovered paths:")
        pprint(custom_asdict(self.discovered_inputs))
        return self.discovered_inputs

    def _discover_user_submitted_paths(self):
        self.discovered_inputs: dict[str, dict[str, DiscoveredInput]] = {
            stage: {} for stage in self.stages
        }
        for stage_name in self.stages:
            if self.loading_info.get(stage_name) is None:
                self.logger.warning(
                    f"No loading info provided for stage '{stage_name}'. "
                    "Skipping input discovery for this stage."
                )
                continue
            for input_spec in getattr(self, f"{stage_name}_stage").implementation.INPUTS:
                discovered_input = self._discover_input(
                    input_spec=input_spec,
                    loading_info=self.loading_info[stage_name],
                )
                if discovered_input is not None:
                    self.discovered_inputs[stage_name][input_spec.name] = discovered_input
                else:
                    self.logger.warning(
                        f"Input '{input_spec.name}' for stage '{stage_name}' "
                        "could not be discovered."
                    )

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
        self.logger.info(f"Directories to search: {loading_info.directories}")

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
            self.logger.warning(f"No file found for '{input_spec.name}'.")
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
    model_name = "model_inhouse_v9_human"
    model_dir = models_dir / model_name
    model_path = model_dir

    expression_path = base_dir / "expression_datasets" / "NCI_60_human"
    # ptr_path = base_dir / "PTR_datasets" / "Eraslan2019_human"
    # proteomics_path = base_dir / "proteomics" / "NCI60"
    output_path = Path("~/git/VmaxBuilder/data/run_example_output")
    create_dynamically_named_results = True
    model_stage_loading_info = StageLoadingInfo(
        stage_name="model",
        directories=model_dir,
        file_paths={
            "smiles_df": model_dir / "smiles_df.csv",
            "transcript_df": model_dir / "transcript_df.csv",
        },
    )

    # Protein inputs (set whichever mode needs).
    stage_implementations = Stages(
        model_implementation=implementations.model.default,
        model_loading_info=model_stage_loading_info,
        # protein_stage=implementations.protein.dummy_protein,
    )
    run_config = RunConfig(
        output_dir=output_path,
        run_name="VmaxBuilder_Run",
        create_dynamically_named_results=create_dynamically_named_results,
        # print_level="DEBUG",
    )

    orchestrator = Orchestrator(stage_implementations, run_config)
    print("showing scaffold user submitted paths: ", orchestrator.scaffold.discovered_inputs)
    print("showing discovered paths: ", orchestrator.return_discovered_paths())
    print("Initial config:")
    orchestrator.show_config()
    print("setting print level to DEBUG...")
    orchestrator.set_print_level("DEBUG")
    print("showing user submitted  paths:")
    orchestrator.return_user_submitted_paths()

    print("setting new  user submitted paths...")
    orchestrator.set_stage_loading_info(
        "model",
        StageLoadingInfo(
            stage_name="model",
            directories=model_dir,
            file_paths={
                "smiles_df": model_dir / "final_SMILES_metabolite_df.csv",
                "transcript_df": model_dir / "final_transcript_df.csv",
            },
        ),
    )
    print("showing updated user submitted paths:")
    orchestrator.return_user_submitted_paths()
    # orchestrator.set_stage_implementation("protein",
    #                                       implementations.protein.proteomic)

    print("Loading inputs...")
    orchestrator.load_inputs()
    print("showing scaffold user submitted paths: ", orchestrator.scaffold.discovered_inputs)
