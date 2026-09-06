import json
import sys
from collections.abc import Iterator
from dataclasses import fields, is_dataclass
from datetime import datetime
from pathlib import Path
from pprint import pprint
from typing import Any, TypeVar, cast, get_type_hints

import pandas as pd

from VmaxBuilder.base.classes import (
    BaseImplementation,
    BaseImplementationDiagnostics,
    _iter_implementations,
)
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
# todo: add, when overwrite is true, and use_previous_run is true,
# a way to utilise already created data and to only validate them


class Orchestrator:
    """Coordinate stage selection, input discovery, execution, and run metadata.

    The orchestrator owns the runtime scaffold and executes the fixed stage order:
    model, protein, allocation, Kcat, Vmax.
    """

    stages = {
        "model": ModelStage,
        "protein": ProteinStage,
        "allocation": AllocationStage,
        "Kcat": KcatStage,
        "Vmax": VmaxStage,
    }

    ImplT = TypeVar("ImplT", bound=BaseImplementation[Any])

    def __init__(self, stage_implementations: StageLoading, run_config: RunConfig):
        """Initialise orchestrator state from loading and run configuration.

        Args:
            stage_implementations (StageLoading): Per-stage loading declarations.
            run_config (RunConfig): Global run behavior and output-path configuration.

        Modifies:
            self.config, self.scaffold, self.loading_info, and internal tracking maps.

        Examples:
            >>> orchestrator = Orchestrator(stage_loading, run_config)
            >>> orchestrator.scaffold.inputs
            {}
        """
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
        """Attach model-stage implementation and refresh model input discovery.

        Args:
            implementation_cls (type[ImplT]): Concrete model implementation class.

        Returns:
            ImplT: Instantiated model implementation.

        Modifies:
            self.model_stage, self.config.model, self.discovered_inputs.

        Examples:
            >>> orchestrator.set_model_implementation(DefaultIrreversibleModelImplementation)
        """
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
        """Attach protein-stage implementation and refresh protein input discovery.

        Args:
            implementation_cls (type[ImplT]): Concrete protein implementation class.

        Returns:
            ImplT: Instantiated protein implementation.

        Modifies:
            self.protein_stage, self.config.protein, self.discovered_inputs.

        Examples:
            >>> orchestrator.set_protein_implementation(
            ...     MvalueTrimmingExpressionPTRImplementation
            ... )
        """
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
        """Attach allocation-stage implementation and refresh allocation discovery.

        Args:
            implementation_cls (type[ImplT]): Concrete allocation implementation class.

        Returns:
            ImplT: Instantiated allocation implementation.

        Modifies:
            self.allocation_stage, self.config.allocation, self.discovered_inputs.

        Examples:
            >>> orchestrator.set_allocation_implementation(FairAllocationImplementation)
        """
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
        """Attach Kcat-stage implementation and refresh Kcat input discovery.

        Args:
            implementation_cls (type[ImplT]): Concrete Kcat implementation class.

        Returns:
            ImplT: Instantiated Kcat implementation.

        Modifies:
            self.Kcat_stage, self.config.Kcat, self.discovered_inputs.

        Examples:
            >>> orchestrator.set_Kcat_implementation(UniKPMainSubstrateImplementation)
        """
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
        """Attach Vmax-stage implementation and refresh Vmax input discovery.

        Args:
            implementation_cls (type[ImplT]): Concrete Vmax implementation class.

        Returns:
            ImplT: Instantiated Vmax implementation.

        Modifies:
            self.Vmax_stage, self.config.Vmax, self.discovered_inputs.

        Examples:
            >>> orchestrator.set_Vmax_implementation(DefaultVmaxReactionResolving)
        """
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
        """Persist orchestrator metadata payload to disk.

        Args:
            metadata (dict[str, Any]): Serializable metadata payload.

        Modifies:
            Writes metadata JSON under run metadata directory.
        """
        metadata_path = self.config.run.paths.metadata_dir / "orchestrator_metadata.json"
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Metadata saved to {metadata_path}")
        with open(metadata_path, "w") as f:
            json.dump(make_json_serializable(metadata), f, indent=4)

    def run(self):
        """Execute the full orchestrator pipeline across all configured stages.

        The run sequence performs discovery, optional dependency checks, optional
        eager loading/validation, then stage execution in fixed order.

        Modifies:
            self.scaffold, output directories, saved metadata, diagnostics, and outputs.

        Examples:
            >>> orchestrator.run()
        """
        start_time = datetime.now()
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

        self.scaffold.extras["_orchestrator_full_run_active"] = True
        try:
            for stage_name in self.stages:
                self.scaffold.extras["_orchestrator_current_stage_name"] = stage_name
                self.scaffold.extras["_orchestrator_future_required_input_names"] = (
                    self._collect_future_stage_required_input_names(stage_name)
                )
                self.logger.info(f"Running stage: {stage_name}")
                self._run_stage(stage_name)
        finally:
            self.scaffold.extras.pop("_orchestrator_current_stage_name", None)
            self.scaffold.extras.pop(
                "_orchestrator_future_required_input_names",
                None,
            )
            self.scaffold.extras.pop("_orchestrator_full_run_active", None)

        elapsed_time = (datetime.now() - start_time).total_seconds()
        self.logger.finished(
            f"Run complete. Finished all stages in {elapsed_time:.2f} seconds.",
            print_level=1,
        )

    def _collect_stage_required_input_names(self, stage_name: str) -> set[str]:
        """Collect required input names for one stage implementation tree.

        Args:
            stage_name (str): Stage key.

        Returns:
            set[str]: Required input names declared by stage consumers.
        """
        stage = getattr(self, f"{stage_name}_stage", None)
        if stage is None:
            return set()

        roots: list[BaseImplementation] = [stage.implementation]
        roots.extend(getattr(stage, "additional_implementations", {}).values())

        required_input_names: set[str] = set()
        for root in roots:
            for implementation in _iter_implementations(root):
                if isinstance(implementation, type):
                    continue

                required_input_names.update(
                    {
                        input_spec.name
                        for input_spec in implementation.INPUTS
                        if input_spec.name
                    }
                )
                for diagnostic in getattr(implementation, "diagnostics", []):
                    diagnostic_obj = cast(BaseImplementationDiagnostics, diagnostic)
                    required_input_names.update(
                        {
                            input_spec.name
                            for input_spec in diagnostic_obj.INPUTS
                            if input_spec.name
                        }
                    )

        return required_input_names

    def _collect_future_stage_required_input_names(
        self,
        current_stage_name: str,
    ) -> set[str]:
        """Collect required input names for stages after current stage.

        Args:
            current_stage_name (str): Current stage key.

        Returns:
            set[str]: Input names required by future stages.
        """
        stage_names = list(self.stages.keys())
        if current_stage_name not in stage_names:
            return set()

        current_index = stage_names.index(current_stage_name)
        required_input_names: set[str] = set()
        for stage_name in stage_names[current_index + 1 :]:
            required_input_names.update(self._collect_stage_required_input_names(stage_name))
        return required_input_names

    def _discover_optional_dependencies(self):
        """Check and optionally install implementation-specific dependencies.

        When one or more optional dependencies are installed, the method exits the
        process so users can restart with newly available modules.

        Raises:
            SystemExit: Raised when optional dependencies were installed.
        """
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
        """Return and optionally print active orchestrator configuration sections.

        Args:
            sections (list[str] | str | None): Section selector. Use None or "all"
                for all sections.
            verbose (bool): Whether to include expanded values in custom serializer.

        Returns:
            dict[str, dict[str, Any]]: Selected configuration sections.

        Raises:
            ValueError: Raised when a requested section is invalid.

        Examples:
            >>> orchestrator.return_config("run")
            >>> orchestrator.return_config(["model", "allocation"])
        """
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
        """Assemble orchestrator-level run metadata.

        Returns:
            dict[str, Any]: Metadata payload with discovered paths and non-default
            configuration values.

        Examples:
            >>> metadata = orchestrator.create_metadata()
            >>> "orchestrator" in metadata
            True
        """
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
        """Return config fields that differ from dataclass defaults.

        Returns:
            dict[str, dict[str, Any]]: Nested map of non-default values with default
            and current entries.

        Examples:
            >>> non_defaults = orchestrator.return_non_default_configs()
            >>> isinstance(non_defaults, dict)
            True
        """
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
        """Replace loading info for one stage and refresh discovered inputs.

        Args:
            stage (str): Stage key.
            loading_info (StageLoadingInfo): New loading declaration.

        Raises:
            ValueError: Raised when stage key is unknown.

        Modifies:
            self.loading_info and self.discovered_inputs.

        Examples:
            >>> orchestrator.set_stage_loading_info(
            ...     "model",
            ...     StageLoadingInfo(stage_name="model", directories=["data/inputs/model"]),
            ... )
        """
        if stage not in self.stages:
            raise ValueError(f"Stage '{stage}' is not a valid stage.")
        self.loading_info[stage] = loading_info
        self._discover_user_submitted_paths(stage_name=stage)

    def _get_all_loggers(self) -> list[CustomLogger]:
        """Collect orchestrator, stage, implementation, and diagnostics loggers.

        Returns:
            list[CustomLogger]: Ordered logger list used for print-level updates.
        """
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
        """Set print verbosity for all loggers attached to current run graph.

        Args:
            level (str | int): One of DEBUG/INFO/WARNING/ERROR/CRITICAL or 4..0.
            log_modification (bool): Whether to emit summary log after applying.

        Raises:
            ValueError: Raised when level has unsupported type or value.

        Modifies:
            All attached loggers and the orchestrator run print-level config.

        Examples:
            >>> orchestrator.set_print_level("DEBUG")
            >>> orchestrator.set_print_level(2)
        """
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
        """Return stage loading declarations currently attached to orchestrator.

        Returns:
            list[PathInfo]: Per-stage path declarations.

        Examples:
            >>> paths = orchestrator.return_user_submitted_paths()
            >>> isinstance(paths, list)
            True
        """
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
        """Load all declared stage inputs into scaffold using selected implementations.

        Modifies:
            self.scaffold.inputs and possibly other scaffold sections through loaders.

        Examples:
            >>> orchestrator.load_inputs()
        """
        for stage_name in self.stages:
            stage = getattr(self, f"{stage_name}_stage")
            stage_implementation: BaseImplementation = stage.implementation
            for implementation in _iter_implementations(stage_implementation):
                if isinstance(implementation, type):
                    continue
                implementation.load_inputs(scaffold=self.scaffold)

    def validate_loaded_inputs(self):
        """Validate loaded inputs against InputSpec validators for each stage.

        Modifies:
            self.validation_results and self.scaffold when optional invalid inputs
            are removed.

        Examples:
            >>> orchestrator.validate_loaded_inputs()
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
        """Run a single stage and update orchestrator scaffold.

        Args:
            stage_name (str): Stage key to execute.

        Modifies:
            self.scaffold.
        """
        # todo: consider whether should be public or private (orchestration run is sequential)
        stage = getattr(self, f"{stage_name}_stage")
        self.scaffold = stage.run(self.scaffold)

    @staticmethod
    def _initialise_scaffold(scaffold: Scaffold | None = None) -> Scaffold:
        """Create an empty scaffold object for runtime data exchange.

        Args:
            scaffold (Scaffold | None): Reserved input. Must be None.

        Returns:
            Scaffold: Newly initialised scaffold.

        Raises:
            ValueError: Raised when scaffold argument is not None.
        """
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
        """Developer hook placeholder for visualising implementation dependency DAG.

        Returns:
            list[tuple[str, str]]: Currently an empty edge list placeholder.
        """
        pass
        dag: list[tuple[str, str]] = []
        return dag

    def validate_virtual_inputs_outputs(self):
        """Developer hook placeholder for static orchestration I/O contract checks."""
        pass

    def _build_default_config(self, run_config: RunConfig) -> FullConfig:
        """Build default full config container from run configuration.

        Args:
            run_config (RunConfig): Run configuration object.

        Returns:
            FullConfig: Config with stage sections initialised to empty
            ImplementationConfig instances.
        """
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
        """Return discovered file-backed inputs grouped by stage.

        Returns:
            dict[str, dict[str, DiscoveredInput]]: Discovered inputs map.

        Examples:
            >>> discovered = orchestrator.return_discovered_paths()
            >>> "model" in discovered
            True
        """
        self.logger.info("Discovered paths:")
        pprint(custom_asdict(self.discovered_inputs))
        return self.discovered_inputs

    def _discover_in_main_implementations(self, stage_name: str):
        """Discover inputs required by selected main implementation tree.

        Args:
            stage_name (str): Stage key.

        Modifies:
            self.discovered_inputs.
        """
        main_implementation = getattr(self, f"{stage_name}_stage").implementation
        self._discover_inputs_in_implementation_tree(
            stage_name=stage_name,
            root_implementation=main_implementation,
        )

    def _discover_in_additional_implementations(self, stage_name: str):
        """Discover inputs required by stage additional implementation trees.

        Args:
            stage_name (str): Stage key.

        Modifies:
            self.discovered_inputs.
        """
        additional_implementations = getattr(
            getattr(self, f"{stage_name}_stage"), "additional_implementations", {}
        )

        if not additional_implementations:
            return

        for additional_implementation in additional_implementations.values():
            self._discover_inputs_in_implementation_tree(
                stage_name=stage_name,
                root_implementation=additional_implementation,
            )

    def _iter_implementation_and_diagnostic_inputs(
        self,
        root_implementation: BaseImplementation,
    ) -> Iterator[tuple[str, InputSpec]]:
        """Yield implementation and diagnostics InputSpec objects with owner labels.

        Args:
            root_implementation (BaseImplementation): Root implementation instance.

        Returns:
            Iterator[tuple[str, InputSpec]]: Owner label and input specification pairs.
        """
        for implementation in _iter_implementations(root_implementation):
            if isinstance(implementation, type):
                continue

            implementation_owner = implementation.__class__.__name__
            for input_spec in implementation.INPUTS:
                yield (implementation_owner, input_spec)

            diagnostics = getattr(implementation, "diagnostics", [])
            for diagnostic in diagnostics:
                diagnostic_obj = cast(BaseImplementationDiagnostics, diagnostic)
                diagnostic_owner = (
                    f"{implementation_owner}.{diagnostic_obj.__class__.__name__}"
                )
                for input_spec in diagnostic_obj.INPUTS:
                    yield (diagnostic_owner, input_spec)

    def _discover_inputs_in_implementation_tree(
        self,
        stage_name: str,
        root_implementation: BaseImplementation,
    ) -> None:
        """Discover files for all InputSpec entries in one implementation tree.

        Args:
            stage_name (str): Stage name used to select loading configuration.
            root_implementation (BaseImplementation): Root implementation instance.
        """
        for owner_name, input_spec in self._iter_implementation_and_diagnostic_inputs(
            root_implementation
        ):
            discovered_input = self._discover_input(
                input_spec=input_spec,
                loading_info=self.loading_info[stage_name],
            )
            if discovered_input is not None:
                self.discovered_inputs[stage_name][input_spec.name] = discovered_input
                self.logger.valid(
                    f"Discovered input '{input_spec.name}' for stage '{stage_name}' "
                    f"in '{owner_name}': {discovered_input.file_path}"
                    f"(source: {discovered_input.source})"
                )
                continue

            attempted_key = f"{stage_name}:{owner_name}:{input_spec.name}"
            if attempted_key in self._attempted_discovered_inputs:
                continue

            self._attempted_discovered_inputs[attempted_key] = input_spec
            self.logger.warning(
                f"Input '{input_spec.name}' for stage '{stage_name}' in '{owner_name}' "
                "could not be discovered."
            )

    def _discover_user_submitted_paths(self, stage_name: str | None = None):
        """Discover user-provided inputs for one stage or all stages.

        Args:
            stage_name (str | None): Optional stage key. When None, refreshes all.

        Modifies:
            self.discovered_inputs.
        """
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
        """Resolve one input specification against explicit paths or search dirs.

        Args:
            input_spec (InputSpec): Input contract to resolve.
            loading_info (StageLoadingInfo): Paths and directories for resolution.

        Returns:
            DiscoveredInput | None: Discovery payload when found, otherwise None.
        """
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
        """Resolve explicit input file path from stage loading info.

        Args:
            input_spec (InputSpec): Input contract.
            loading_info (StageLoadingInfo): Stage loading declaration.

        Returns:
            Path | None: Existing absolute path or None when unresolved.
        """
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
        """Normalize directory declarations into resolved Path list.

        Args:
            directories (list[Path | str] | Path | str | None): Raw directory setting.

        Returns:
            list[Path]: Resolved directory paths.
        """
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
        """Search configured directories for files matching one InputSpec.

        Args:
            input_spec (InputSpec): Input contract with prefix/extensions.
            loading_info (StageLoadingInfo): Directory declarations.

        Returns:
            Path | None: Best match according to extension priority.
        """
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
        """Return files in one directory that match InputSpec prefix/extensions.

        Args:
            directory (Path): Directory to scan.
            input_spec (InputSpec): Input contract with prefix/extensions.

        Returns:
            list[Path]: Candidate file paths.
        """
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
        """Select best file match, preferring InputSpec extension order.

        Args:
            matches (list[Path]): Candidate matches.
            input_spec (InputSpec): Input contract containing extension priority.

        Returns:
            Path | None: Selected file path or None.
        """
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

    expression_name = "DCM_magnet"
    expression_path = base_dir / "expression_datasets" / expression_name
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

    trim_enable = True
    trim_name = "trim" if trim_enable else "no_trim"
    run_config = RunConfig(
        output_dir=output_path,
        run_name=f"{trim_name}_{expression_name}_{model_name}_run",
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

    nci60_to_eraslan_tissues = {
        # Breast Cancer (BR) -> endometrium / ovary / fat (Endometrium/ovary is used for
        # female reproductive origin, but fat or lymph node is sometimes grouped; here
        # matched to ovary/endometrium, or commonly grouped broadly. Let's map to
        # endometrium/ovary or the closest matching glandular tissue like endometrium)
        "BR:BT-549": "endometrium",
        "BR:HS 578T": "endometrium",
        "BR:MCF7": "endometrium",
        "BR:MDA-MB-231": "endometrium",
        "BR:T-47D": "endometrium",
        # Central Nervous System (CNS) -> brain
        "CNS:SF-268": "brain",
        "CNS:SF-295": "brain",
        "CNS:SF-539": "brain",
        "CNS:SNB-19": "brain",
        "CNS:SNB-75": "brain",
        "CNS:U251": "brain",
        # Colon Cancer (CO) -> colon
        "CO:COLO 205": "colon",
        "CO:HCC-2998": "colon",
        "CO:HCT-116": "colon",
        "CO:HCT-15": "colon",
        "CO:HT29": "colon",
        "CO:KM12": "colon",
        "CO:SW-620": "colon",
        # Lung Cancer (LC) -> lung
        "LC:A549/ATCC": "lung",
        "LC:EKVX": "lung",
        "LC:HOP-62": "lung",
        "LC:HOP-92": "lung",
        "LC:NCI-H226": "lung",
        "LC:NCI-H23": "lung",
        "LC:NCI-H322M": "lung",
        "LC:NCI-H460": "lung",
        "LC:NCI-H522": "lung",
        # Leukemia (LE) -> lymph node (or spleen/tonsil; lymph node is the standard baseline
        # representation for white blood cells/lymphoid lineages)
        "LE:CCRF-CEM": "lymphnode",
        "LE:HL-60(TB)": "lymphnode",
        "LE:K-562": "lymphnode",
        "LE:MOLT-4": "lymphnode",
        "LE:RPMI-8226": "lymphnode",
        "LE:SR": "lymphnode",
        # Melanoma (ME) -> fat (Melanoma originates in the skin, which is not directly
        # present as "skin" in the 29 tissues. The subcutaneous layer or closest
        # lipid/epithelial proxy often leans toward fat or smooth muscle; fat is the standard
        # substitute here)
        "ME:LOX IMVI": "fat",
        "ME:M14": "fat",
        "ME:MALME-3M": "fat",
        "ME:MDA-MB-435": "fat",
        "ME:MDA-N": "fat",
        "ME:SK-MEL-2": "fat",
        "ME:SK-MEL-28": "fat",
        "ME:SK-MEL-5": "fat",
        "ME:UACC-257": "fat",
        "ME:UACC-62": "fat",
        # Ovarian Cancer (OV) -> ovary
        "OV:IGROV1": "ovary",
        "OV:NCI/ADR-RES": "ovary",
        "OV:OVCAR-3": "ovary",
        "OV:OVCAR-4": "ovary",
        "OV:OVCAR-5": "ovary",
        "OV:OVCAR-8": "ovary",
        "OV:SK-OV-3": "ovary",
        # Prostate Cancer (PR) -> prostate
        "PR:DU-145": "prostate",
        "PR:PC-3": "prostate",
        # Renal Cancer (RE) -> kidney
        "RE:786-0": "kidney",
        "RE:A498": "kidney",
        "RE:ACHN": "kidney",
        "RE:CAKI-1": "kidney",
        "RE:RXF 393": "kidney",
        "RE:SN12C": "kidney",
        "RE:TK-10": "kidney",
        "RE:UO-31": "kidney",
    }
    if expression_name == "NCI_60_human":
        # ty: ignore
        protein.config.expression_sample_type_map = nci60_to_eraslan_tissues
    else:
        protein.config.expression_sample_type_map = {idx: "heart" for idx in range(1, 1000)}

    protein.config.PTR_special_gene_groups = {"transport_reactions": []}
    # todo: rename use_special_groups_for_unobserved_imputation to PTR

    protein.config.use_special_groups_for_unobserved_imputation = True
    protein.config.trim_enable = trim_enable

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
