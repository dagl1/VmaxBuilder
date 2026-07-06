import inspect
import json
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, fields, is_dataclass, make_dataclass
from datetime import datetime
from inspect import getmembers, isfunction
from pprint import pprint
from typing import TYPE_CHECKING, Any, Generic, Iterator, ParamSpec, TypeVar

if TYPE_CHECKING:
    from VmaxBuilder.base.configs import FullConfig
from VmaxBuilder.base.exceptions import ImplementationConfigConflictError
from VmaxBuilder.utils.custom_logging import CustomLogger, custom_asdict

if TYPE_CHECKING:
    from VmaxBuilder.base.configs import (
        InputSpec,
        OutputSpec,
        Scaffold,
    )

ConfigType = TypeVar("ConfigType")

P = ParamSpec("P")
R = TypeVar("R")


class BaseStage:
    STAGE_NAME: str
    DIAGNOSTICS = []
    NECESSARY_OUTPUTS: list["OutputSpec"] = []
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
        self.logger = CustomLogger(f"Fallback logger: {self.STAGE_NAME}")

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
        for diagnostic in self.DIAGNOSTICS:
            diagnostic.before_run(scaffold)

        # Run the implementation
        scaffold = self.implementation.run(scaffold)
        scaffold = self.run_additional_processes(scaffold)

        # Run diagnostics after the stage execution
        for diagnostic in self.DIAGNOSTICS:
            diagnostic.after_run(scaffold)

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

        for output_spec in self.NECESSARY_OUTPUTS:
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
                (is_valid, return_message) = output_spec.validator(output_value)
                if not is_valid:
                    raise ValueError(
                        f"Validation failed for necessary output '{output_spec.name}'. "
                        f"Validator returned message: {return_message}"
                    )


class BaseStageDiagnostics:
    """
    Only used for implementation-independent diagnostics used to verify stage output
    based on stage contracts.
    """

    def after_run(self, scaffold): ...


class ImplementationDiagnostics:
    """
    Used for implementation-specific diagnostics, which may include verifying
    stage output but also more detailed checks that may be specific
    to the implementation's approach.
    """

    def before_run(self, scaffold): ...
    def after_run(self, scaffold): ...
    def on_error(self, error): ...


class BaseImplementation(Generic[ConfigType], ABC):
    STAGE_NAME: str
    IMPL_NAME: str

    BASE_STAGE_CONFIG: type | None = None
    IMPLEMENTATION_CONFIG_CLASS: type | None = None
    _RESOLVED_CONFIG_CLASS: type | None = None

    INPUTS: list["InputSpec"] = []
    OUTPUTS: list["OutputSpec"] = []

    CHILD_IMPLEMENTATIONS: list[type["BaseImplementation"]] = []

    DIAGNOSTICS: list[ImplementationDiagnostics] = []

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
        self.logger = CustomLogger(f"Fallback logger: {self.IMPL_NAME}")
        self.full_config = full_config
        self.config: ConfigType = resolve_implementation_config_class(
            full_config, self.__class__, self.BASE_STAGE_CONFIG
        )()

    @abstractmethod
    def generate_outputs(self, scaffold: "Scaffold") -> dict[str, Any]:
        """
        Generate outputs based on the scaffold and return them as a dictionary.
        The keys of the dictionary should match the names of the outputs defined in OUTPUTS.
        This allows for all implementations and child implementations to a checkable contract
        for what they will produce before run-time. Each generate outputs can be checked
        in order, and a DAG can be created to follow the dependencies of each output.
        """
        ...

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
            new_scaffold_objects = self.generate_outputs(scaffold)
            new_scaffold_objects = self.add_stage_to_scaffold(new_scaffold_objects)
            self.save_artifacts_and_outputs(new_scaffold_objects)
            scaffold.update_scaffold(new_scaffold_objects)
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
            if scaffold.get_scaffold_location(input_spec.name):
                # If the input is already present in the scaffold, skip loading
                continue
            elif (
                input_spec.name
                and input_spec.loader
                and input_spec.name in scaffold.discovered_inputs[self.STAGE_NAME]
            ):
                file_path = scaffold.discovered_inputs[self.STAGE_NAME][
                    input_spec.name
                ].file_path
                loaded_input = input_spec.loader(
                    file_path,
                    **(input_spec.loader_args or {}),
                )
                scaffold.inputs[input_spec.name] = loaded_input
            elif not input_spec.optional:
                raise ValueError(f"Cannot load input '{input_spec.name}': ")
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
        (is_valid, return_message) = input_spec.validator(input_value)
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
        self, scaffold: "Scaffold", location="inputs"
    ) -> tuple["Scaffold", list[dict[str, str | bool]]]:
        """
        Validate the inputs in the scaffold against the INPUTS specification. This should
        not be overwritten, validation functions are added to input specs.
        """
        validation_results: list[dict[str, str | bool]] = []
        for input_spec in self.INPUTS:
            (scaffold, validation_result) = self.validate_input(
                scaffold=scaffold, input_spec=input_spec, location=location
            )
            if validation_result is None:
                continue

            validation_results.append(
                {
                    "input_name": input_spec.name,
                    "is_valid": validation_result["is_valid"],
                    "return_message": validation_result["return_message"],
                    "call_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            )

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

    def add_stage_to_scaffold(self, new_scaffold_objects) -> dict[str, Any]:
        stage_name = f"{self.STAGE_NAME}_stage"
        for key, value in new_scaffold_objects.items():
            if stage_name not in value:
                value[stage_name] = {}
            value[stage_name].update(value.pop(key, {}))

        return new_scaffold_objects

    def save_artifacts_and_outputs(self, scaffold_objects: dict[str, Any]) -> None:
        """
        For each output, use the specified saver to save the output to disk.
        For each artifact, use the specified saver to save the artifact to disk, if
        missing a function (not specified,) save it as a json file.
        This is implementation-agnostic, and thus will be handled per stage.
        Stages save metadata, and diagnostics, while outputs and artifacts are saved at the
        end of an implmentation run
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
        only save artifacts if artifact saving is enabled (in run_config, although we check
        if the CombinedConfig of the stage has a save_artifacts attribute, and it is not
        set to none, we then use that value for that specific stage to override it
        """
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
                            artifact_spec.saver(
                                save_location / f"{artifact_name}{artifact_spec.extension}",
                                **(artifact_spec.saver_args or {}),
                            )
                        else:
                            self.logger.warning(
                                f"No saver specified for artifact '{artifact_name}'. "
                                "Saving as JSON by default."
                            )
                            with open(save_location / f"{artifact_name}.json", "w") as f:
                                json.dump(artifact_value, f)

            elif key == "outputs":
                output_folder = self.full_config.run.paths.outputs_dir
                for _, outputs in value.items():
                    for output_name, output_value in outputs.items():
                        output_spec = next(
                            (spec for spec in self.OUTPUTS if spec.name == output_name),
                            None,
                        )
                        if output_spec and output_spec.saver:
                            output_spec.saver(
                                output_folder / f"{output_name}{output_spec.extension}",
                                **(output_spec.saver_args or {}),
                            )
                        else:
                            self.logger.warning(
                                f"No saver specified for output '{output_name}'. "
                                "Saving as JSON by default."
                            )

                            with open(f"{output_name}.json", "w") as f:
                                json.dump(output_value, f)


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


def resolve_implementation_config_class(
    full_config: "FullConfig",
    impl_cls: type["BaseImplementation"],
    core_config_cls: type | None = None,
) -> type:
    stage_configs = []

    for impl in _iter_implementations(impl_cls):
        config_cls = getattr(impl, "IMPLEMENTATION_CONFIG_CLASS", None)
        if config_cls is not None:
            stage_configs.append(config_cls)

    if core_config_cls is not None:
        stage_configs.append(core_config_cls)

    validate_config_conflicts(stage_configs)

    return build_flattened_config(stage_configs, full_config=full_config)


@dataclass(slots=True)
class ImplementationConfig:
    pass


def build_flattened_config(config_classes: list[type], full_config: "FullConfig") -> type:
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
    if not combined_fields:
        raise ValueError("No fields found in the provided config classes.")

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
