import inspect
from dataclasses import asdict, dataclass, field, fields, is_dataclass, make_dataclass
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
can provide a dictionary with filepaths for each input spec of a specific stage.

add check if at least one dir or path is provided
then search based on inputs if not found we raise error

"""


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
        self.logger = CustomLogger("Orchestrator")
        self.discovered_inputs: dict[str, dict[str, Path | None]] = {
            stage: {} for stage in self.stages
        }
        self.config = self._build_default_config(run_config=run_config)

        # get user input for loading and implementations
        self.loading_info = {
            stage: getattr(stage_implementations, f"{stage}_loading_info")
            for stage in self.stages
        }
        self._resolve_stage_implementations(stage_implementations=stage_implementations)
        self._discover_user_submitted_paths()

    def show_config(self, sections: list[str] | str | None = None):
        if not hasattr(self.config, "run") or self.config.run is None:
            raise ValueError(
                "Config must have a 'run' section witha valid RunConfig instance."
            )
        if (sections is not None) and not isinstance(sections, (str, list)):
            raise ValueError("Sections must be None, a string, or a list of strings.")

        elif sections is None:
            pprint(asdict(self.config))
        elif isinstance(sections, str):
            pprint(asdict(getattr(self.config, sections)))
        elif isinstance(sections, list):
            for section in sections:
                if not hasattr(self.config, section):
                    raise ValueError(f"Section '{section}' not found in config.")
                allowed_types = tuple(f.type for f in fields(self.config))
                if not isinstance(getattr(self.config, section), allowed_types):
                    raise ValueError(f"Section '{section}' is not a valid config section.")
                pprint(asdict(getattr(self.config, section)))

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
        config_cls = self._get_implementation_config_class(implementation=impl_cls)
        setattr(
            self,
            f"{stage}_stage",
            getattr(self, f"{stage}_stage").__class__(impl_cls, config_cls),
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
                        filepaths=loading_info.filepaths,
                    )
                )
        self.logger.info(
            "User submitted paths:"
            f"{[asdict(path_info) for path_info in user_submitted_paths]}"
        )

        return user_submitted_paths

    @staticmethod
    def _initialise_scaffold(scaffold: Scaffold | None = None) -> Scaffold:
        if scaffold is None:
            return {
                "inputs": {},
                "artifacts": {},
                "outputs": {},
                "metadata": {},
                "diagnostics": {},
                "extras": {},
            }
        scaffold.setdefault("inputs", {})
        scaffold.setdefault("artifacts", {})
        scaffold.setdefault("outputs", {})
        scaffold.setdefault("metadata", {})
        scaffold.setdefault("diagnostics", {})
        scaffold.setdefault("extras", {})
        return scaffold

    def _resolve_stage_implementations(self, stage_implementations: Stages):
        for stage in self.stages:
            impl_name = getattr(stage_implementations, f"{stage}_implementation")
            impl_cls = self._resolve_implementation(stage, impl_name)
            config_cls = self._get_implementation_config_class(implementation=impl_cls)
            setattr(
                self,
                f"{stage}_stage",
                self.stages[stage](impl_cls, config_cls),
            )

    def _resolve_implementation(self, stage: str, impl_name: str) -> type[BaseImplementation]:
        key = f"{stage}:{impl_name}"
        if key not in self.registry:
            raise ValueError(f"Implementation '{impl_name}' for stage '{stage}' not found.")
        return self.registry[key]

    def _get_implementation_config_class(
        self,
        *,
        implementation: type[BaseImplementation] | None = None,
        stage: str | None = None,
        impl_name: str | None = None,
    ) -> type | None:
        if implementation is not None:
            return getattr(implementation, "CONFIG_CLASS", None)

        if stage is None or impl_name is None:
            raise ValueError(
                "Either 'implementation' or both 'stage' and 'impl_name' must be provided."
            )

        impl_cls = self._resolve_implementation(stage, impl_name)
        stage_configs = self._collect_implementation_configs(impl_cls)
        self._validate_config_conflicts(stage_configs)
        flattened_stage_config = self._build_flattened_config(stage_configs)

        return flattened_stage_config

    def _collect_implementation_configs(
        self,
        implementation: type[BaseImplementation],
    ) -> list[type]:
        configs = []

        config_cls = getattr(
            implementation,
            "CONFIG_CLASS",
            None,
        )

        if config_cls is not None:
            configs.append(config_cls)

        for (
            child_stage,
            child_impl_name,
        ) in implementation.CHILD_IMPLEMENTATIONS.items():
            child_impl = self._resolve_implementation(
                child_stage,
                child_impl_name,
            )

            configs.extend(self._collect_implementation_configs(child_impl))

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

    def _discover_user_submitted_paths(self):
        self.discovered_inputs = {
            stage_name: {
                input_spec.name: self._discover_input(
                    input_spec=input_spec,
                    loading_info=self.loading_info[stage_name],
                )
                for input_spec in getattr(
                    self,
                    f"{stage_name}_stage",
                ).implementation.INPUTS
            }
            for stage_name in self.stages
            if self.loading_info.get(stage_name)
        }

    def _discover_input(self, input_spec, loading_info) -> Path | None:
        if (
            input_spec.loader is None
            or input_spec.file_key is None
            or input_spec.extensions is None
        ):
            return None
        explicit_path = self._resolve_explicit_filepath(
            input_spec,
            loading_info,
        )

        if explicit_path is not None:
            return explicit_path

        return self._search_directories(
            input_spec,
            loading_info,
        )

    def _resolve_explicit_filepath(
        self,
        input_spec: InputSpec,
        loading_info: StageLoadingInfo,
    ) -> Path | None:
        filepaths = loading_info.filepaths or {}

        if input_spec.name not in filepaths:
            return None

        path = Path(filepaths[input_spec.name]).expanduser().resolve()

        if not path.exists():
            print(f"[WARNING] File not found for '{input_spec.name}': {path}")
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

        for directory in self._normalize_directories(loading_info.directories):
            if not directory.exists():
                print(f"[WARNING] Directory not found: {directory}")
                continue

            matches.extend(
                self._find_matching_files(
                    directory,
                    input_spec,
                )
            )

        return self._select_match(
            matches,
            input_spec.name,
        )

    def _find_matching_files(
        self,
        directory: Path,
        input_spec: InputSpec,
    ) -> list[Path]:
        matches = []
        if input_spec.file_key is None or input_spec.extensions is None:
            return matches

        for extension in input_spec.extensions:
            matches.extend(directory.glob(f"{input_spec.file_key}*{extension}"))

        return matches

    def _select_match(
        self,
        matches: list[Path],
        input_name: str,
    ) -> Path | None:
        if len(matches) == 0:
            print(f"[WARNING] No file found for '{input_name}'.")
            return None

        if len(matches) > 1:
            print(
                f"[WARNING] Multiple files found "
                f"for '{input_name}'. "
                f"Using first match:\n"
                f"{matches}"
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
        filepaths={
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
    )

    orchestrator = Orchestrator(stage_implementations, run_config)
    # orchestrator.config.model.
