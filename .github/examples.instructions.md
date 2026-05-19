# Key examples

## API

```python

class RouteOptimisationMethod(Enum):
    INVERSE = "inverse"
    FLUX_WEIGHTED = "flux_weighted"
    MINIMUM_FLUX = "minimum_flux"
    MINIMUM_REACTIONS = "minimum_reactions"
    BOTTLENECK_MAXIMISATION = "bottleneck_maximisation"
    CELLFIE = "cellfie"

@runtime_checkable
class RouteOptimisationProtocol(Protocol):
    """Public surface that every registered route optimisation strategy must expose."""

    def run_optimisation(
        self,
        route_model: Any,
        settings: dict[str, Any],
    ) -> None: ...

    @staticmethod
    def objective_method(
        py_model: ConcreteModel | None = None,
        reaction_ids: list[str] | None = None,
        constant_reactions: list[int] | None = None,
        reaction_expression: dict[int, float] | None = None,
    ) -> Objective | float: ...

class BaseRouteOptimiser(_RouteModelScaffoldMixin, ABC):
    """Base strategy scaffold with stable public methods and private hooks."""

    # METHOD_NAME: str | None = None

    def __init__(self) -> None:
        # Core injects its logger instance; this fallback keeps strategy usage robust.
        self.logger = CustomLogger("route_optimization_strategy")

    def run_optimisation(
        self,
        route_model: Any,
        settings: dict[str, Any],
    ) -> None:
        self._run_optimisation_loop(route_model, settings)

    def _modify_route_model_for_next_sample(
        self, route_model: dict[str, Any], sample_index: int
    ) -> None:
        self._apply_sample_expression_for_sample(
            route_model,
            sample_index,
            settings=route_model.get("settings", {}),
        )
        self._refresh_persistent_solver_for_sample_update(route_model)

    def _modify_route_model_for_next_task(
        self, route_model: dict[str, Any], task_index: int
    ) -> None:
        self._transition_to_task(
            route_model,
            task_index,
            route_model["task_structure"],
            route_model.get("settings", {}),
        )



@register_method(group="route_optimiser", name="flux_weighted")
class FluxWeightedRouteOptimiser(BaseRouteOptimiser):
    # for baserouteoptimizer

    @staticmethod
    def objective_method(
        py_model: ConcreteModel | None = None,
        reaction_expression: dict[str, float] | None = None,
        **kwargs: Any,
    ) -> float | Objective:
        """
        This publuc method is used to allow for a method to call to get the objective given a
        set of reactions and their activity, should also be used for setting objective in
        _create_route_model. Thus should set both py_model objective, or return the
        objective calculated from
        """
        if py_model is not None:
            return Objective(
                expr=quicksum(
                    py_model.constant_reaction_fluxes[idx]  # ty: ignore
                    / pyo.value(py_model.reaction_expression[idx])  # ty: ignore
                    for idx in py_model.constant_reactions  # ty: ignore
                ),
                sense=minimize,
            )
        elif reaction_expression is not None and kwargs.get("flux_values"):
            flux_values: dict[int, float] = kwargs["flux_values"]
            return sum(
                flux_values[idx] / reaction_expression[idx] for idx in reaction_expression
            )
        else:
            raise ValueError(
                "Must provide either all arguments or just the ones needed to calculate "
                "objective value."
            )

@dataclass
class SolverConfig:
    """Solver identity and numerical tolerances."""

    name: str = "gurobi_persistent"
    time_limit: int | None = None
    integrality_focus: int = 0
    int_feas_tol: float = 1e-5
    options: dict[str, Any] = field(default_factory=dict)
    minimal_accepted_penalty_value: float = 1e-5


@dataclass
class ExpressionConfig:
    """Controls how raw expression data is transformed and mapped to reactions."""

    promiscuity_method: str = "N"  # todo
    # "activity" or "log_activity"
    activity_transformation: str = "activity"
    epsilon: float = 1e-4
    expressionless_reaction_value: float = 0.001

@dataclass
class RouteOptimizationConfig:
    """
    Top-level configuration for RouteOptimization.

    All fields have sensible defaults so the object can be constructed with no
    arguments and then selectively overridden:

        config = RouteOptimizationConfig()
        config.solver.name = "cplex"
        config.run.tasks = [1, 2, 3]
    """

    solver: SolverConfig = field(default_factory=SolverConfig)
    expression: ExpressionConfig = field(default_factory=ExpressionConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    run: RunConfig = field(default_factory=RunConfig)
    output: OutputConfig = field(default_factory=OutputConfig)

class RouteOptimization:
    """
    PCA-style interface for route optimisation.

    Typical usage — folder mode::

        optimizer = RouteOptimization(
            method=RouteOptimisationMethod.INVERSE,
            config=RouteOptimizationConfig(),
        )
        optimizer.load(preprocessing_folder="data/preprocessing/my_run")
        optimizer.run()

    Step-by-step (build model first, solve separately)::

        optimizer.load(preprocessing_folder="data/preprocessing/my_run")
        model = optimizer.create_route_model()    # returns the route model
        optimizer.run_optimisation(model)         # solve it

    Explicit paths::

        optimizer.load(
            model_path="data/models/my_model.json",
            expression_data_path="data/expression/my_expr.json",
            tasklist_path="data/tasklists/my_tasks.json",
        )

    In-memory objects::

        optimizer.load(cobra_model=model, expression_data=df, tasklist=task_dict)

    Mixed — folder base with expression override::

        optimizer.load(
            preprocessing_folder="data/preprocessing/my_run",
            expression_data=my_new_df,
        )

    Config overrides::

        config = RouteOptimizationConfig()
        config.solver.name = "cplex"
        config.run.tasks = [1, 2, 3]
        optimizer = RouteOptimization(method="flux_weighted", config=config)
    """

    def __init__(
        self,
        method: str | RouteOptimisationMethod = RouteOptimisationMethod.FLUX_WEIGHTED,
        activity_transformation: str | ActivityTransformation | None = None,
        config: RouteOptimizationConfig | None = None,
    ) -> None:
        self.config: RouteOptimizationConfig = (
            config if config is not None else load_route_optimization_config()
        )
        self.method = get_route_optimisation_method(method)
        # Keep `.method` as alias to the selected objective for API convenience.
        if activity_transformation is None:
            parsed_transformation = parse_activity_transformation(
                self.config.expression.activity_transformation
            )
        else:
            parsed_transformation = parse_activity_transformation(activity_transformation)
        # Persist one canonical representation in config.
        self.config.expression.activity_transformation = parsed_transformation.value
        # Strategy is instantiated eagerly to validate method dispatch at construction.
        self._strategy = self._instantiate_strategy(self.method)
        # grab the print level from config for use in the logger
        print_level = self.config.run.print_level
        self.logger = CustomLogger(
            "route_optimization",
            print_level=print_level,
        )
        self._strategy.logger = self.logger
        self._input: RouteOptimizationInput | None = None
        # Set by create_route_model(); holds the strategy-specific model object.
        self.route_model_: Any = None

    def _resolve_run_output_root(self) -> Path:
        run_name = str(self.config.run.name_of_run)
        configured = self.config.output.result_output_folder
        if configured is not None:
            return Path(configured) / run_name
        if self._input is not None:
            return self._input.get_effective_preprocessing_folder() / "Results" / run_name
        return Path.cwd() / "Results" / run_name

    def _sync_logger_output_location(self) -> None:
        run_root = self._resolve_run_output_root()
        if hasattr(self.logger, "set_log_files_location"):
            self.logger.set_log_files_location(str(run_root))

    def _instantiate_strategy(self, objective: RouteOptimisationMethod) -> BaseRouteOptimiser:
        """Instantiate the strategy class for the selected optimisation objective."""
        strategy_class: Type[BaseRouteOptimiser] = get_method(
            "route_optimiser", objective.value
        )
        return strategy_class()

if __name__ == "__main__":
    root = get_project_root()
    data_folder = root / "data"
    preprocessing_folder = data_folder / "for_VmaxBuilder" / "combinations"
    preprocessing_name = ("model_inhouse_v9_human_Amsterdam_collab_ # pragma: allowlist secret
       tasklist_MACSBIO_v0_6_6_20260210_Eraslan2019V1_UniKPV1" # pragma: allowlist secret
    ) #pragma: allowlist secret
    preprocessing_folder = preprocessing_folder / preprocessing_name
    output_folder = data_folder / "VmaxBuilder_results"

    # Load the config, adjust it as needed:
    config = load_route_optimization_config()
    config.run.name_of_run = "new_API_weighted_flux_amsterdam_collab"
    config.run.print_level = 2
    config.run.tasks = list(range(18, 100))
    config.run.samples = list(range(1, 10))
    config.solver.name = "gurobi_persistent"
    config.run.generate_task_sample_artifacts = True
    # config.run.start_first_task_from_sample = 3

    # Load the optimization class with the config:
    optimizer = RouteOptimization(config=config, method="flux_weighted")

    # Example of adjusting the config after loading it, but before running the optimization:
    optimizer.config.output.result_output_folder = output_folder

    # Load the preprocessing data and run the optimization:
    optimizer.load(preprocessing_folder=preprocessing_folder)
    optimizer.run()
```

## Documentation

```Python

def compare_runs(
    self,
    comparison_runs: Dict[str, pd.DataFrame | str | pathlib.Path | Dict[str, Any]],
    output_location: Optional[Union[str, pathlib.Path]] = None,
    base_options_dict: Optional[Dict] = None,
    create_specific_samples: Optional[List[int]] = None,
    use_specific_samples: Optional[List[int]] = None,
    **kwargs,
):
    """

    This function will compare the reaction activity distributions of different preprocessing
    runs, e.g. expression only, expression + ptr, expression + ptr + kcat.
    It will create several plots for comparisons and save them in the current folder if no
    output location has been provided. The inputs can be provided as a dict in the format:
    { "<name of run>": <reaction_activity_df> }.
    or
    { "<name of run>": <path to reaction_activity_df file> }.
    or
    { "<name of run>": options dict to create the reaction_activity_df> }.

    A combination of these can be used, in which case the function will open any files first,
    then attempt to create a new reaction_activity_df including a combination folder (if such
    already exists that might become overwritten depending on the options).

    To not recreate large options dictionaries, for each run, a base_options_dict can be provided
    which will be used as a base and only the options that differ from the base will be
    updated in the PreprocessingPipeline instance.

    If create_specific_samples is provided, only those samples will be created for the comparison.
    This can be useful as recreation of large reaction_activity_df files can take a long time
    and generally only a few samples will be required to be compared.

    If use_specific_samples is provided, only those samples will be used for the comparison.
    Otherwise all samples will be used and this might lead to longer computation times.

    Args:
        comparison_runs (dict[str, pd.DataFrame | str | pathlib.Path | Dict[str, Any]]):
            A dictionary containing the names of the runs as keys and either the reaction_activity_df
            as values, or the path to the reaction_activity_df file, or a dict of options to create
            the reaction_activity_df.
        output_location (Union[str, pathlib.Path]): The location where the comparison plots
            will be saved. If not provided, the current folder will be used.
        base_options_dict (Optional[dict[str, Any]]): A dictionary containing the base options to be used
            for creating new reaction_activity_df files. If not provided, the default options
            will be used.
        create_specific_samples (Optional[list[int]]): A list of sample indices to be created
            for the comparison. If not provided, all samples will be created.
        use_specific_samples (Optional[list[int]]): A list of sample indices to be used
            for the comparison. If not provided, all samples will be used.
        **kwargs: Additional keyword arguments to be passed to the InputComparisonDiagnostics class.

    Requires:
        self.reaction_activity_name: str: The name of the reaction activity column in the reaction_activity_df files.
        self.reaction_id_column_name: str: The name of the reaction id column in the reaction_activity_df files.
        self.sample_id_column_name: str: The name of the sample id column in the reaction_activity_df files.

    Modifies:
        self.paths: list[Path]: Potentially already created paths for the reaction_activity_df files of the runs to b
        e compared, if these are not provided as dataframes in the comparison_runs dict. If these files do not already
        exist, they will be created and added to the paths list. If they already exist, they will be added to the
        paths list and might become overwritten depending on the options provided.


    Returns:
        None: The function will save the comparison plots in the current folder or in the

    Important:
        When creating only a specific selection of samples, if these overwrite previous runs
        in which all samples were prepared, you will lose the previous preprocessing runs.
        If you already have created all samples and only want to compare a few of them,
        you can select their dataframes in the comparison_runs dict directly, and set
        use_specific_samples to only compare those samples.

    """
```
