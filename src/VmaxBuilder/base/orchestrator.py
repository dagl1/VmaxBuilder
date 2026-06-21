from dataclasses import asdict, dataclass, field
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
    Paths,
    RunConfig,
    StageLoadingInfo,
    Stages,
)
from VmaxBuilder.base.registry import IMPLEMENTATION_REGISTRY
from VmaxBuilder.stages.model.model import ModelStage
from VmaxBuilder.utils.custom_logging import CustomLogger

run_config_type_hints = get_type_hints(RunConfig)
PrintLevelType = run_config_type_hints.get("print_level", str)


class Orchestrator:
    registry: dict[str, type[BaseImplementation]] = IMPLEMENTATION_REGISTRY
    stages = ["model"]

    def __init__(self, stage_implmentations: Stages, run_config: RunConfig):
        self.logger = CustomLogger("Orchestrator")
        self.discovered_inputs: dict[str, dict[str, Path | None]] = {
            stage: {} for stage in self.stages
        }
        self.loading_info = {
            stage: getattr(stage_implmentations, f"{stage}_loading_info")
            for stage in self.stages
        }
        model_stage_implementation = self._resolve_implementation(
            "model", stage_implmentations.model_implementation.value
        )
        model_stage_config = self._get_implementation_config_class(
            implementation=model_stage_implementation,
        )

        self.model_stage = ModelStage(model_stage_implementation, model_stage_config)
        self.config = self._build_default_config(run_config=run_config)
        self._discover_user_submitted_paths()

    def show_config(self, sections: list[str] | str | None = None):
        if sections is None:
            pprint(asdict(self.config))
        elif isinstance(sections, str):
            pprint(asdict(getattr(self.config, sections)))
        elif isinstance(sections, list):
            for section in sections:
                if not hasattr(self.config, section):
                    raise ValueError(f"Section '{section}' not found in config.")
                if not isinstance(
                    getattr(self.config, section), (ImplementationConfig, RunConfig, Paths)
                ):
                    raise ValueError(f"Section '{section}' is not a valid config section.")
                pprint(asdict(getattr(self.config, section)))
        raise ValueError("Sections must be None, a string, or a list of strings.")

    def set_results_dir(self, path: Path):
        self.config.paths.results_dir = path

    def set_stage_loading_info(self, stage: str, loading_info: StageLoadingInfo):
        if stage not in self.stages:
            raise ValueError(f"Stage '{stage}' is not a valid stage.")
        self.loading_info[stage] = loading_info
        self._discover_user_submitted_paths()

    def set_stage_implementation(
        self,
        stage: str,
        implmentation_name: MODEL_IMPLEMENTATIONS
        | PROTEIN_IMPLEMENTATIONS
        | ALLOCATION_IMPLEMENTATIONS,
    ):
        if stage not in self.stages:
            raise ValueError(f"Stage '{stage}' is not a valid stage.")
        impl_cls = self._resolve_implementation(stage, implmentation_name.value)
        config_cls = self._get_implementation_config_class(implementation=impl_cls)
        setattr(
            self,
            f"{stage}_stage",
            getattr(self, f"{stage}_stage").__class__(impl_cls, config_cls),
        )

        self.logger.info(
            f"Set implementation for stage '{stage}' to '{implmentation_name.value}'."
        )

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
        self.config.run.print_level = cast(PrintLevelType, level_literal)

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
        return getattr(impl_cls, "CONFIG_CLASS", None)

    def _build_default_config(self, run_config: RunConfig) -> FullConfig:
        return FullConfig(
            model=ImplementationConfig(),
            run=run_config,
            paths=Paths(_results_dir=run_config.output_dir),
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
    """
    Users can provide one or more directories for a specific stage, in which all inputspes
    with their denoted extension and file keys will be sought. Alternatively users
    can provide a dictionary with filepaths for each input spec of a specific stage.

    add check if at least one dir or path is provided
    then search based on inputs if not found we raise error

    """

    # Protein inputs (set whichever mode needs).
    stage_implmentations = Stages(
        model_implementation=implementations.model.default,
        model_loading_info=model_stage_loading_info,
        # protein_stage=implementations.protein.dummy_protein,
    )
    run_config = RunConfig(
        output_dir=output_path,
        run_name=model_name,
        create_dynamically_named_results=create_dynamically_named_results,
    )
    orchestrator = Orchestrator(stage_implmentations, run_config)
    # orchestrator.config.model.
