import inspect
import json
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from dataclasses import (
    dataclass,
    field,
    fields,
    is_dataclass,
    make_dataclass,
)
from datetime import datetime
from hashlib import new
from inspect import getmembers, isfunction
from lib2to3.pytree import Base
from pathlib import Path
from pprint import pformat, pprint
from typing import TYPE_CHECKING, Any, Generic, Iterator, ParamSpec, TypeVar

import pandas as pd

from VmaxBuilder.base.exceptions import ImplementationConfigConflictError
from VmaxBuilder.utils.custom_logging import CustomLogger, custom_asdict
from VmaxBuilder.utils.file_handling import save_with_tries
from VmaxBuilder.utils.iterables import make_json_serializable

if TYPE_CHECKING:
    from VmaxBuilder.base.configs import (
        FullConfig,
        InputSpec,
        OutputSpec,
        Scaffold,
    )

ConfigType = TypeVar("ConfigType")

P = ParamSpec("P")
R = TypeVar("R")

fallback_logger = CustomLogger("Fallback logger: BaseStage & BaseImplementation")


class BaseStage:
    STAGE_NAME: str
    DIAGNOSTICS: list[type["BaseStageDiagnostics"]] = []
    OUTPUTS: list["OutputSpec"] = []
    CORE_CONFIG_CLASS = None
    ADDITIONAL_IMPLEMENTATIONS: list[type["BaseImplementation"]] = []

    def __init__(self, implementation: "BaseImplementation", config: "FullConfig"):
        """Generated: validation needed.

        Description:
            Initialise stage wrapper with concrete implementation and full config.

        Args:
            implementation (BaseImplementation): Stage implementation instance.
            config (FullConfig): Full run configuration.
        """
        self.config = config
        self.implementation = implementation
        self.additional_implementations = {
            # class name of implementation: instance of implementation
            impl.__name__: impl(config)
            for impl in self.ADDITIONAL_IMPLEMENTATIONS
        }
        self.diagnostics = [diag() for diag in self.DIAGNOSTICS]
        self.logger = CustomLogger(f"{self.STAGE_NAME}_stage_logger")

    def run(self, scaffold):
        """Generated: validation needed.

        Description:
            Execute diagnostics hooks around implementation run and return scaffold.

        Args:
            scaffold (Scaffold): Shared scaffold payload.

        Returns:
            Scaffold: Updated scaffold after stage execution.
        """
        # Run diagnostics before the stage execution
        for diagnostic in self.diagnostics:
            diagnostic.before_run(scaffold)

        # Run the implementation
        scaffold = self.implementation.run(scaffold)
        scaffold = self.run_additional_processes(scaffold)

        # Run diagnostics after the stage execution
        # todo: debug here or somewhat earlier, appears that scaffold is modified
        # by run additional processes, irreversible_cobra_model disappears
        for diagnostic in self.diagnostics:
            diagnostic.after_run(scaffold)

        self.ensure_outputs(scaffold)

        return scaffold

    def run_additional_processes(self, scaffold: "Scaffold") -> "Scaffold":
        """
        Run any additional processes after the implementation has run.
        This is implementation-agnostic, and thus will be handled per stage.
        """
        return scaffold

    def ensure_outputs(self, scaffold: "Scaffold") -> None:
        """
        Ensure that all necessary outputs are present in the scaffold.
        If any necessary output is missing, raise a ValueError.
        """

        for output_spec in self.OUTPUTS:
            if (
                output_spec.name not in scaffold.outputs
                and output_spec.name not in scaffold.inputs
            ):
                raise ValueError(
                    f"Necessary output '{output_spec.name}' is missing from the scaffold."
                )
            if output_spec.validator:
                output_value = scaffold.outputs.get(output_spec.name) or scaffold.inputs.get(
                    output_spec.name
                )
                validator_args = output_spec.validator_args or {}
                accepted_args = inspect.signature(output_spec.validator).parameters
                filtered_validator_args = {
                    k: v for k, v in validator_args.items() if k in accepted_args
                }

                (is_valid, return_message) = output_spec.validator(
                    output_value, **filtered_validator_args
                )
                if not is_valid:
                    raise ValueError(
                        f"Validation failed for necessary output '{output_spec.name}'. "
                        f"Validator returned message: {return_message}"
                    )


class BaseStageDiagnostics(ABC):
    """
    Only used for implementation-independent diagnostics used to verify stage output
    based on stage contracts.
    """

    DIAGNOSTICS_NAME: str

    @abstractmethod
    def after_run(self, scaffold: "Scaffold"): ...

    @abstractmethod
    def before_run(self, scaffold: "Scaffold"): ...


@dataclass(slots=True)
class DiagnosticOutputSpec:
    data: Any
    save_file_name: str
    extensions: list[str] | str
    data_type: type | None = None
    saver: Callable = save_with_tries
    saver_args: dict[str, Any] = field(default_factory=dict)  # additional args


class BaseImplementationDiagnostics(Generic[ConfigType], ABC):
    """
    Used for implementation-specific diagnostics, which may include verifying
    stage output but also more detailed checks that may be specific
    to the implementation's approach.
    """

    DIAGNOSTICS_NAME: str

    def __init__(self, full_config: "FullConfig"):
        self.full_config = full_config
        self.logger = CustomLogger(f"{self.DIAGNOSTICS_NAME}_diagnostics_logger")

    @abstractmethod
    def before_run(
        self,
        scaffold: "Scaffold",
    ) -> dict[str, dict[str, Any]]: ...
    @abstractmethod
    def after_run(
        self,
        new_scaffold_objects: dict[str, dict[str, Any]],
        scaffold: "Scaffold",
    ) -> dict[str, dict[str, Any]]: ...

    # def on_error(self, scaffold: dict[str, dict[str, Any]], error: Exception):
    #     ...  # todo: implement this, unsure how exactly
    #     # maybe through a context manager  or by returning
    #     # specific errors. ALternatively we could have
    #     # specific custom exceptions that call the on_error
    #     # method when raised
    # decorator for taking all values in the return of a function
    # and putting them into the format of diagnosticoutputspec

    def create_diagnostics_outputs(
        self,
        func: Callable[..., dict[str, Any] | Any | tuple[Any, ...]],
        save_file_name: str,
        extensions: list[str] | str,
        data_type: type | None = None,
        saver: Callable = save_with_tries,
        saver_args: dict[str, Any] | None = None,
    ) -> Callable[..., list[DiagnosticOutputSpec]]:
        if saver_args is None:
            saver_args = {}

        def wrapper(*args, **kwargs) -> list[DiagnosticOutputSpec]:
            outputs = func(*args, **kwargs)

            if isinstance(outputs, dict):
                return [
                    DiagnosticOutputSpec(
                        data=value,
                        save_file_name=f"{save_file_name}_{key}",
                        extensions=extensions,
                        data_type=data_type,
                        saver=saver,
                        saver_args=saver_args if saver_args is not None else {},
                    )
                    for key, value in outputs.items()
                ]
            elif isinstance(outputs, (list, tuple)):
                return [
                    DiagnosticOutputSpec(
                        data=value,
                        save_file_name=f"{save_file_name}_n{i}",
                        extensions=extensions,
                        data_type=data_type,
                        saver=saver,
                        saver_args=saver_args if saver_args is not None else {},
                    )
                    for i, value in enumerate(outputs)
                ]
            else:
                return [
                    DiagnosticOutputSpec(
                        data=outputs,
                        save_file_name=save_file_name,
                        extensions=extensions,
                        data_type=data_type,
                        saver=saver,
                        saver_args=saver_args if saver_args is not None else {},
                    )
                ]

        return wrapper


class BaseImplementation(Generic[ConfigType], ABC):
    STAGE_NAME: str
    IMPL_NAME: str

    BASE_STAGE_CONFIG: type | None = None
    IMPLEMENTATION_CONFIG_CLASS: type | None = None
    _RESOLVED_CONFIG_CLASS: type | None = None

    INPUTS: list["InputSpec"] = []
    OUTPUTS: list["OutputSpec"] = []

    CHILD_IMPLEMENTATIONS: list[type["BaseImplementation"]] = []

    DIAGNOSTICS: list[type["BaseImplementationDiagnostics"]] = []

    def __init__(
        self,
        full_config: "FullConfig",
    ):
        """Generated: validation needed.

        Description:
            Initialise implementation with shared configuration and child implementations.

        Args:
            full_config (FullConfig): Full run configuration object.
        """
        self.child_implementations = [
            impl(full_config) for impl in self.CHILD_IMPLEMENTATIONS
        ]
        self.logger = CustomLogger(f"{self.IMPL_NAME}_implementation_logger")
        self.full_config = full_config
        self.diagnostics = [diag(full_config) for diag in self.DIAGNOSTICS]
        self.config: ConfigType = resolve_implementation_config_class(
            self,
            self.BASE_STAGE_CONFIG,
            # child_implementations=self.child_implementations,
        )()

    def generate_outputs(self, scaffold: "Scaffold") -> dict[str, dict[str, Any]]:
        return {}

    def run_before_diagnostics(
        self,
        scaffold: "Scaffold",
    ) -> dict[str, dict[str, Any]]:
        """
        Run diagnostics before generating outputs. This is implementation-agnostic,
        and thus will be handled per stage.
        """

        scaffold_objects: dict[str, dict[str, Any]] = {
            "diagnostics": {},
        }
        for diagnostic in self.diagnostics:
            scaffold_objects = diagnostic.before_run(scaffold)

        return scaffold_objects

    def run_after_diagnostics(
        self,
        scaffold_objects: dict[str, dict[str, Any]],
        scaffold: "Scaffold",
    ) -> dict[str, dict[str, Any]]:
        """
        Run diagnostics after generating outputs. This is implementation-agnostic,
        and thus will be handled per stage.
        """
        new_scaffold_objects = {
            "outputs": {},
            "artifacts": {},
            "diagnostics": {},
            "metadata": {},
        }
        for diagnostic in self.diagnostics:
            new_scaffold_objects = diagnostic.after_run(scaffold_objects, scaffold=scaffold)
        return new_scaffold_objects

    def run(self, scaffold: "Scaffold") -> "Scaffold":
        """Generated: validation needed.

        Description:
            Execute current implementation or recursively execute child implementations.

        Args:
            scaffold (Scaffold): Shared scaffold payload.

        Returns:
            Scaffold: Updated scaffold.
        """
        if not self.child_implementations:
            # before_run diagnostics
            before_run_scaffold_objects = self.run_before_diagnostics(scaffold)
            before_run_scaffold_objects = self.add_stage_and_run_moment_to_scaffold(
                before_run_scaffold_objects, "before_run"
            )
            scaffold.update_scaffold(before_run_scaffold_objects)
            self.save_all_scaffold_objects(before_run_scaffold_objects)

            # output generation
            during_run_scaffold_objects = self.generate_outputs(scaffold)
            during_run_scaffold_objects = self.add_stage_and_run_moment_to_scaffold(
                during_run_scaffold_objects, "during_run"
            )
            scaffold.update_scaffold(during_run_scaffold_objects)
            self.save_all_scaffold_objects(during_run_scaffold_objects)

            # after_run diagnostics
            after_run_scaffold_objects = self.run_after_diagnostics(
                during_run_scaffold_objects, scaffold
            )
            after_run_scaffold_objects = self.add_stage_and_run_moment_to_scaffold(
                after_run_scaffold_objects, "after_run"
            )
            scaffold.update_scaffold(after_run_scaffold_objects)
            self.save_all_scaffold_objects(after_run_scaffold_objects)

        else:
            for child_impl in self.child_implementations:
                scaffold = child_impl.run(scaffold)

        return scaffold

    def load_inputs(self, scaffold: "Scaffold") -> None:
        """Generated: validation needed.

        Description:
            Load stage inputs into scaffold using discovered input file paths and loaders.

        Args:
            scaffold (Scaffold): Shared scaffold payload.

        Raises:
            KeyError: Raised when `self.STAGE_NAME` key is absent in
                `scaffold.discovered_inputs`.
            ValueError: Raised when required input cannot be loaded.
        """
        for input_spec in self.INPUTS:
            if input_spec.in_scaffold:
                # If the input is already present in the scaffold, skip loading
                continue
            elif scaffold.get_scaffold_location(input_spec.name):
                # If the input is already present in the scaffold, skip loading
                continue
            elif (
                input_spec.name
                and input_spec.loader
                and input_spec.name in scaffold.discovered_inputs[self.STAGE_NAME]
            ):
                accepted_args = inspect.signature(input_spec.loader).parameters
                filtered_loader_args = {
                    k: v
                    for k, v in (input_spec.loader_args or {}).items()
                    if k in accepted_args
                }
                file_path = scaffold.discovered_inputs[self.STAGE_NAME][
                    input_spec.name
                ].file_path
                loaded_input = input_spec.loader(file_path, **filtered_loader_args)
                scaffold.inputs[input_spec.name] = loaded_input
            elif not input_spec.optional:
                class_name = self.__class__.__name__
                stage_name = self.STAGE_NAME

                logger_message = (
                    f"Full input specification: \n{pformat(input_spec)}.\n\n"
                    f"Full discovered inputs: \n{pformat(scaffold.discovered_inputs)}.\n"
                )
                self.logger.error(logger_message)
                implementation_file = inspect.getfile(self.__class__)
                implemenation_class_line_number = inspect.getsourcelines(self.__class__)[1]

                file_location = (
                    f'File "{implementation_file}:{implemenation_class_line_number}"'
                )

                error_message = (
                    f"Required input '{input_spec.name}' is missing for stage '{stage_name}' "
                    f"implemented by '{class_name}'\n {file_location} . \n"
                    "Please ensure that the input is provided in the scaffold or "
                    "that a fallback provider is available to supply the input.\n"
                )
                raise ValueError(error_message)
            else:
                continue

    def validate_input(
        self, scaffold: "Scaffold", input_spec: "InputSpec", location="inputs"
    ) -> tuple["Scaffold", dict[str, bool | str] | None]:
        """Generated: validation needed.

        Description:
            Validate single input spec from scaffold, with fallback from inputs to outputs.

        Args:
            scaffold (Scaffold): Shared scaffold payload.
            input_spec (InputSpec): Input specification including validator.
            location (str): Scaffold section to inspect first.

        Returns:
            tuple[Scaffold, dict[str, bool | str] | None]: Scaffold and validation result.
        """
        FALLBACK_LOCATION = "outputs"
        if not input_spec.validator:
            self.logger.warning(
                f"No validator specified for input '{input_spec.name}'. "
                "Skipping validation for this input."
            )
            return (scaffold, None)

        if (
            input_spec.name not in getattr(scaffold, location)
            and location == FALLBACK_LOCATION
        ):
            self.logger.warning(
                f"Input '{input_spec.name}' is not present in the scaffold. "
                "Skipping validation for this input."
            )
            return (scaffold, None)

        elif input_spec.name not in getattr(scaffold, location):
            return self.validate_input(
                scaffold=scaffold,
                input_spec=input_spec,
                location=FALLBACK_LOCATION,
            )

        input_value = getattr(scaffold, location)[input_spec.name]
        validator_args = input_spec.validator_args or {}
        accepted_args = inspect.signature(input_spec.validator).parameters
        filtered_validator_args = {
            k: v for k, v in validator_args.items() if k in accepted_args
        }

        (is_valid, return_message) = input_spec.validator(
            input_value, **filtered_validator_args
        )
        if not is_valid:
            self.logger.error(
                f"Validation failed for input '{input_spec.name}'. "
                f"Validator returned message: {return_message}"
                "Please check the input value and ensure it meets the expected criteria."
                "In case the input is optional, it is removed from scaffold "
                "and might be provided by a fallback provider."
            )
            if input_spec.optional:
                self.logger.warning(
                    f"Input '{input_spec.name}' is optional. "
                    "Removing it from the scaffold to allow for fallback providers."
                )
                del scaffold.inputs[input_spec.name]
        elif is_valid:
            self.logger.info(
                f"Validation successful for input '{input_spec.name}'. "
                f"Validator returned message: {return_message}"
                "Input meets the expected criteria."
            )
        return (scaffold, {"is_valid": is_valid, "return_message": return_message})

    def validate_inputs(
        self,
        already_validated_inputs: dict[str, "InputSpec"],
        scaffold: "Scaffold",
        location="inputs",
    ) -> tuple["Scaffold", list[dict[str, str | bool]]]:
        """
        Validate the inputs in the scaffold against the INPUTS specification. This should
        not be overwritten, validation functions are added to input specs.
        """
        validation_results: list[dict[str, str | bool]] = []
        for input_spec in self.INPUTS:
            if input_spec.name in already_validated_inputs:
                continue

            (scaffold, validation_result) = self.validate_input(
                scaffold=scaffold, input_spec=input_spec, location=location
            )
            if validation_result is None:
                continue

            validation_results.append(
                {
                    "stage_name": self.STAGE_NAME,
                    "implementation_name": self.IMPL_NAME,
                    "input_name": input_spec.name,
                    "is_valid": validation_result["is_valid"],
                    "return_message": validation_result["return_message"],
                    "call_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
            already_validated_inputs[input_spec.name] = input_spec

        return (scaffold, validation_results)

    def get_implementation_config_params(self, section: str | None = None) -> dict[str, Any]:
        if section is not None:
            current_stage_config = getattr(self.full_config, section)
        else:
            current_stage_config = getattr(self.full_config, self.STAGE_NAME)
        self.logger.info(
            f"Current stage config for '{self.STAGE_NAME}':"
            f" {custom_asdict(current_stage_config)}"
        )
        return custom_asdict(current_stage_config)

    @staticmethod
    def get_time_decorator(func: Callable[P, R]) -> Callable[P, tuple[float, R]]:
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> tuple[float, R]:
            start_time = datetime.now()
            result = func(*args, **kwargs)
            end_time = datetime.now()
            elapsed_time = (end_time - start_time).total_seconds()
            return elapsed_time, result

        return wrapper

    def add_diagnostic_modifier_to_scaffold(
        self, new_scaffold_objects: dict[str, dict[str, Any]], diagnostic_addition: str
    ) -> dict[str, Any]:
        for key, value in list(new_scaffold_objects.items()):
            # if isinstance(value, dict) and diagnostic_addition in value:
            #     continue
            # elif key == "outputs":
            #     continue
            if key != "diagnostics":
                continue
            new_scaffold_objects[key] = {diagnostic_addition: value}

        return new_scaffold_objects

    def add_stage_to_scaffold(
        self, new_scaffold_objects: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        stage_name = f"{self.STAGE_NAME}_stage"

        for key, value in list(new_scaffold_objects.items()):
            if isinstance(value, dict) and stage_name in value:
                continue
            elif key == "outputs":
                continue
            new_scaffold_objects[key] = {stage_name: value}

        return new_scaffold_objects

    def add_stage_and_run_moment_to_scaffold(
        self,
        new_scaffold_objects: dict[str, dict[str, Any]],
        run_moment: str,
    ) -> dict[str, Any]:
        new_scaffold_objects = self.add_diagnostic_modifier_to_scaffold(
            new_scaffold_objects, run_moment
        )
        new_scaffold_objects = self.add_stage_to_scaffold(new_scaffold_objects)
        return new_scaffold_objects

    def save_artifacts(self, scaffold_objects: dict[str, Any]) -> None:
        for key, value in scaffold_objects.items():
            if key == "artifacts" and (
                getattr(self.config, "save_artifacts", None) is True
                or (
                    getattr(self.config, "save_artifacts", None) is None
                    and self.full_config.run.save_artifacts
                )
            ):
                artifact_folder = self.full_config.run.paths.artifacts_dir
                for stage_name, artifacts in value.items():
                    artifact_stage_folder = artifact_folder / stage_name
                    artifact_stage_folder.mkdir(parents=True, exist_ok=True)
                    for artifact_name, artifact_value in artifacts.items():
                        save_location = artifact_stage_folder / f"{artifact_name}"
                        artifact_spec = next(
                            (spec for spec in self.OUTPUTS if spec.name == artifact_name),
                            None,
                        )
                        if artifact_spec and artifact_spec.saver:
                            saver_args = artifact_spec.saver_args or {}
                            saver_args["overwrite"] = (
                                self.full_config.run.overwrite_existing_results
                            )
                            saver_args["logger"] = self.logger
                            accepted_args = inspect.signature(artifact_spec.saver).parameters
                            filtered_saver_args = {
                                k: v for k, v in saver_args.items() if k in accepted_args
                            }
                            artifact_spec.saver(
                                artifact_value,
                                save_location.with_suffix(artifact_spec.extension),
                                **filtered_saver_args,
                            )
                        else:
                            self.logger.warning(
                                f"No saver specified for artifact '{artifact_name}'. "
                                "Saving as JSON by default."
                            )
                            save_location.with_suffix(".json")
                            with open(save_location, "w") as f:
                                json.dump(make_json_serializable(artifact_value), f)

    def save_outputs(self, scaffold_objects: dict[str, Any]) -> None:
        """
        For each output, use the specified saver to save the output to disk.
        For each artifact, use the specified saver to save the artifact to disk, if
        missing a function (not specified,) save it as a json file.
        This is implementation-agnostic, and thus will be handled per stage.
        Stages save metadata, and diagnostics, while outputs and artifacts are saved at the
        end of an implementation run
        artifacts go into their own stage  folders:
        main_folder/artifacts/stage_name/artifact_name
        while outputs go into their own stage folders:
        main_folder/outputs/output_name without the stage.
        the scaffold objects at this point look like:
        {
                "artifacts": {stage_name: {artifact_name: artifact_value}},
                "outputs": {stage_name: {output_name: output_value}},
                "metadata": {stage_name: {metadata_name: metadata_value}},
                "diagnostics": {stage_name: {diagnostic_name: diagnostic_value}},
        }
        only save artifacts if artifact saving is enabled; in run_config, although we check
        if the CombinedConfig of the stage has a save_artifacts attribute, and it is not
        set to none, we then use that value for that specific stage to override it
        """
        exempted_data_types = {pd.DataFrame, pd.Series}
        for key, value in scaffold_objects.items():
            if key == "outputs":
                output_folder = self.full_config.run.paths.outputs_dir
                for output_name, output_value in value.items():
                    output_spec = next(
                        (spec for spec in self.OUTPUTS if spec.name == output_name),
                        None,
                    )
                    if output_spec and output_spec.saver:
                        if output_spec.save_file_name:
                            output_name = output_spec.save_file_name

                        saver_args = output_spec.saver_args or {}
                        saver_args["overwrite"] = (
                            self.full_config.run.overwrite_existing_results
                        )
                        saver_args["logger"] = self.logger
                        accepted_args = inspect.signature(output_spec.saver).parameters
                        filtered_saver_args = {
                            k: v for k, v in saver_args.items() if k in accepted_args
                        }
                        output_spec.saver(
                            output_value,
                            output_folder / f"{str(output_name)}{output_spec.extension}",
                            **filtered_saver_args,
                        )
                    else:
                        self.logger.warning(
                            f"No saver specified for output '{output_name}'. "
                            "Saving as JSON by default."
                        )
                        output_name = (
                            output_spec.save_file_name
                            if output_spec and output_spec.save_file_name
                            else output_name
                        )
                        save_location = output_folder / f"{str(output_name)}.json"
                        if type(output_value) in exempted_data_types:
                            if isinstance(output_value, pd.DataFrame):
                                output_value.to_csv(save_location.with_suffix(".csv"))
                        else:
                            with open(save_location, "w") as f:
                                json.dump(make_json_serializable(output_value), f)

    def save_diagnostics(
        self,
        scaffold_objects: dict[str, Any],
    ) -> None:
        """
        Save diagnostics to disk.

        Folder structure:

            diagnostics/
                <stage_name>/
                    before_run/
                        <location>/
                            ...
                    during_run/
                        <location>/
                            ...
                    after_run/
                        <location>/
                            ...
        """
        diagnostics = scaffold_objects.get("diagnostics")
        if not diagnostics:
            return

        diagnostic_stage_folder = (
            self.full_config.run.paths.diagnostics_dir / f"{self.STAGE_NAME}_stage"
        )

        stage_diagnostics = diagnostics.get(f"{self.STAGE_NAME}_stage", {})

        for diagnostic_time in ("before_run", "during_run", "after_run"):
            time_diagnostics = stage_diagnostics.get(diagnostic_time)
            if not time_diagnostics:
                continue

            diagnostic_time_folder = diagnostic_stage_folder / diagnostic_time

            for location, value in time_diagnostics.items():
                diagnostic_location_folder = diagnostic_time_folder / location
                diagnostic_location_folder.mkdir(parents=True, exist_ok=True)

                if isinstance(value, Mapping):
                    outputs = [(key, val) for key, val in value.items()]

                elif isinstance(value, list):
                    outputs = [
                        (
                            getattr(
                                diagnostic,
                                "save_file_name",
                                f"{location}_{i}",
                            ),
                            diagnostic,
                        )
                        for i, diagnostic in enumerate(value)
                    ]

                else:
                    outputs = [(location, value)]

                for diagnostic_name, diagnostic_value in outputs:
                    if isinstance(diagnostic_value, list):
                        for i, diagnostic in enumerate(diagnostic_value):
                            self._save_specific_diagnostic(
                                diagnostic_value=diagnostic,
                                save_location=diagnostic_location_folder,
                                diagnostic_name=f"{diagnostic_name}_{i}",
                            )
                    else:
                        self._save_specific_diagnostic(
                            diagnostic_value=diagnostic_value,
                            save_location=diagnostic_location_folder,
                            diagnostic_name=diagnostic_name,
                        )

    def _save_specific_diagnostic(
        self,
        diagnostic_value: Any,
        save_location: Path,
        diagnostic_name: str,
    ) -> None:
        """
        Save a single diagnostic object.
        """

        if isinstance(diagnostic_value, DiagnosticOutputSpec):
            saver_args = diagnostic_value.saver_args or {}
            saver_args["overwrite"] = self.full_config.run.overwrite_existing_results
            saver_args["extension"] = diagnostic_value.extensions
            saver_args["logger"] = self.logger
            accepted_args = inspect.signature(diagnostic_value.saver).parameters
            filtered_saver_args = {k: v for k, v in saver_args.items() if k in accepted_args}

            diagnostic_value.saver(
                diagnostic_value.data,
                save_location / f"{diagnostic_value.save_file_name}",
                **filtered_saver_args,
            )
            return

        with (save_location / f"{diagnostic_name}.json").open(
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                make_json_serializable(diagnostic_value),
                f,
                indent=2,
            )

    def save_metadata(
        self,
        scaffold_objects: dict[str, Any],
    ) -> None:
        """
        Save metadata to disk. This is implementation-agnostic,
        and thus will be handled per stage.
        Metadata go into their own stage folders:
            main_folder/metadata/stage_name/metadata_name
        """
        metadata_folder = self.full_config.run.paths.metadata_dir
        metadata = scaffold_objects.get("metadata", None)
        if metadata:
            metadata_stage_folder = metadata_folder / f"{self.STAGE_NAME}_stage"
            metadata_stage_folder.mkdir(parents=True, exist_ok=True)
            stage_metadata = metadata.get(f"{self.STAGE_NAME}_stage", {})
            for metadata_name, metadata_value in stage_metadata.items():
                save_location = metadata_stage_folder / f"{metadata_name}.json"
                # todo: add way to indicate save_with_tries and extension
                with open(save_location, "w") as f:
                    json.dump(make_json_serializable(metadata_value), f)

    # def _recurse_dictionary_until_leaf(
    #     self, node: dict[str, Any], current_path: Path
    #     ) -> None:

    def save_all_scaffold_objects(self, scaffold_objects: dict[str, Any]) -> None:
        """
        Save all scaffold objects (artifacts, outputs, diagnostics, metadata) to disk.
        This is implementation-agnostic, and thus will be handled per stage.
        """
        self.save_artifacts(scaffold_objects)
        self.save_outputs(scaffold_objects)
        self.save_diagnostics(scaffold_objects)
        self.save_metadata(scaffold_objects)


def validate_config_conflicts(
    config_classes: list[type],
):
    # todo: move to utils and remove from here and orchestrator
    key_owners = {}
    for config_cls in config_classes:
        source_file = inspect.getfile(config_cls)
        _, line_number = inspect.getsourcelines(config_cls)
        if not is_dataclass(config_cls):
            raise TypeError(
                f"Config class '{config_cls.__name__}' in {source_file} is not a dataclass."
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
                if previous["config"] == config_cls:
                    fallback_logger.debug(
                        f"Duplicate config key '{_field.name}'"
                        "found in the same config class "
                        f"{config_cls.__name__} in {source_file}:{line_number}. "
                        "This is allowed as they are identical."
                    )
                    continue

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


class RealImplementation(BaseImplementation[ConfigType], Generic[ConfigType]):
    def __init__(
        self,
        full_config: "FullConfig",
    ):
        super().__init__(full_config)

    @abstractmethod
    def generate_outputs(self, scaffold: "Scaffold") -> dict[str, dict[str, Any]]:
        """
        Generate outputs based on the scaffold and return them as a dictionary.
        The keys of the dictionary should match the names of the outputs defined in OUTPUTS.
        This allows for all implementations and child implementations to a checkable contract
        for what they will produce before run-time. Each generate outputs can be checked
        in order, and a DAG can be created to follow the dependencies of each output.
        """
        ...

    @abstractmethod
    def create_metadata(self, elapsed_time: float, **kwargs) -> dict[str, Any]: ...


def resolve_implementation_config_class(
    implementation: "BaseImplementation",
    core_config_cls: type | None = None,
    # child_implementations: list["BaseImplementation"],
) -> type:
    stage_configs = []

    fallback_logger.debug(
        f"Resolving config for implementation: {implementation.__class__.__name__}"
    )
    for impl in _iter_implementations(implementation):
        config_cls = getattr(impl, "IMPLEMENTATION_CONFIG_CLASS", None)
        if config_cls is not None:
            fallback_logger.debug(
                f"Found config class: {config_cls.__name__}"
                f"for implementation: {impl.__class__.__name__}"
            )
            stage_configs.append(config_cls)

    if core_config_cls is not None:
        stage_configs.append(core_config_cls)

    validate_config_conflicts(stage_configs)

    return build_flattened_config(stage_configs)


@dataclass(slots=True)
class ImplementationConfig:
    pass


def build_flattened_config(config_classes: list[type]) -> type:
    combined_fields = []

    already_seen_configs = set()

    for config_cls in config_classes:
        # We have already validated that there are no conflicts with duplicate
        # fields, with the exception of identical config classes.
        if config_cls in already_seen_configs:
            continue
        already_seen_configs.add(config_cls)

        for _field in fields(config_cls):  # ty: ignore
            combined_fields.append(
                (
                    _field.name,
                    _field.type,
                    _field,
                )
            )

    if not combined_fields:
        return ImplementationConfig

    # if combined fields includes save_artifacts, set it to None so that user
    # must specifically overwrite it in order for it to be set to True or False
    # This is to avoid accidentally saving artifacts when not intended.

    if any(field[0] == "save_artifacts" for field in combined_fields):
        combined_fields = [
            (name, typ, field) if name != "save_artifacts" else (name, typ, None)
            for name, typ, field in combined_fields
        ]
    return make_dataclass(
        cls_name="CombinedConfig",
        fields=combined_fields,
        bases=(ImplementationConfig,),
        slots=True,
    )


@dataclass(frozen=True)
class FallbackProviderMetadata:
    provides: str
    requires: frozenset[str]


def fallback_provider(
    provides: str,
    requires: set[str] | None = None,
):
    """Generated: validation needed.

    Description:
        Mark method as fallback provider for scaffold value discovery.

    Args:
        provides (str): Scaffold key produced by provider.
        requires (set[str] | None): Required scaffold keys before provider can run.

    Returns:
        Callable[[Callable[..., Any]], Callable[..., Any]]: Decorator attaching metadata.
    """
    requires_frozen = frozenset(requires or ())

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        setattr(  # noqa
            func,
            "_fallback_provider",
            FallbackProviderMetadata(provides=provides, requires=requires_frozen),
        )
        return func

    return decorator


def get_fallback_providers(cls):
    """Generated: validation needed.

    Description:
        Collect fallback provider metadata from class methods.

    Args:
        cls (type): Class containing potential fallback provider methods.

    Returns:
        dict[str, FallbackProviderMetadata]: Provider metadata keyed by provided key.
    """
    providers = {}

    for _, method in getmembers(cls, isfunction):
        metadata = getattr(method, "_fallback_provider", None)

        if metadata is not None:
            providers[metadata.provides] = metadata

    return providers


def _iter_implementations(
    implementation: type["BaseImplementation"] | BaseImplementation,
) -> Iterator[BaseImplementation | type["BaseImplementation"]]:
    yield implementation

    child_implementations: list[BaseImplementation] = getattr(
        implementation, "child_implementations", []
    )

    for child_implementation in child_implementations:
        yield from _iter_implementations(child_implementation)
