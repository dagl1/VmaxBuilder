import logging
from typing import Literal

from pyomo.environ import ConcreteModel, SolverFactory
from pyomo.opt import SolverResults
from pyomo.opt.base.solvers import OptSolver, SolverFactoryClass

# todo: we need to add imports for the different solvers / check if they are installed
# # todo: figure out how to add  optional dependencies to uv
ProblemType = Literal["LP", "QP"]

# Data-driven solver hierarchy (ordered by preference)
QP_SOLVERS = [
    "gurobi_persistent",
    "cplex_persistent",
    "gurobi",
    "cplex",
    "ipopt",
]
LP_SOLVERS = [
    "gurobi_persistent",
    "cplex_persistent",
    "gurobi",
    "cplex",
    "glpk",
]

logger = logging.getLogger(__name__)

ProblemType = Literal["LP", "QP"]
SOLVER_PREFERENCE: dict[ProblemType, list[str]] = {
    "LP": [
        "gurobi_persistent",
        "cplex_persistent",
        "gurobi",
        "cplex",
        "highs",
        "glpk",
    ],
    "QP": [
        "gurobi_persistent",
        "gurobi",
        "cplex_persistent",
        "cplex",
        "ipopt",
    ],
}

PERSISTENT_SOLVERS = {
    "gurobi_persistent",
    "cplex_persistent",
}


def get_valid_solver(
    problem_type: ProblemType,
    persistent: bool = False,
) -> tuple[OptSolver, bool]:
    """
    Return the highest-priority available solver.

    Returns
    -------
    solver:
        Instantiated Pyomo solver.
    persistent:
        Whether the solver uses Pyomo's persistent interface.
    """
    lookup_type = problem_type.upper()

    if lookup_type not in SOLVER_PREFERENCE:
        raise ValueError(f"Unknown problem type: '{problem_type}'. Choose 'LP' or 'QP'.")

    for solver_name in SOLVER_PREFERENCE[lookup_type]:
        if persistent and solver_name not in PERSISTENT_SOLVERS:
            continue
        if not persistent and solver_name in PERSISTENT_SOLVERS:
            continue
        try:
            solver = SolverFactory(solver_name)

            if solver is None:
                continue

            if solver.available(exception_flag=False):
                persistent = solver_name in PERSISTENT_SOLVERS

                logger.info(
                    "Selected solver '%s' for %s (%s).",
                    solver_name,
                    lookup_type,
                    "persistent" if persistent else "non-persistent",
                )

                return solver, persistent

        except Exception as exc:
            logger.debug(
                "Solver '%s' unavailable: %s",
                solver_name,
                exc,
            )

    raise RuntimeError(
        f"No valid {lookup_type} solver is available. Tried: {SOLVER_PREFERENCE[lookup_type]}"
    )


def solve_model(
    solver: OptSolver,
    model: ConcreteModel,
    persistent: bool,
) -> SolverResults:
    """
    Solve a Pyomo model using either a persistent or non-persistent solver.
    """

    if persistent:
        solver.set_instance(model)
        return solver.solve()

    return solver.solve(model)


def get_valid_solver_factory(problem_type: ProblemType) -> SolverFactoryClass | OptSolver:
    """
    Returns an available Pyomo SolverFactory based on the problem type.
    Prioritizes premium commercial solvers, falling back to free alternatives.
    """
    # Safeguard against casing issues
    lookup_type = problem_type.upper()  # type: ignore

    if lookup_type not in SOLVER_PREFERENCE:
        raise ValueError(f"Unknown problem type: '{problem_type}'. Choose 'LP' or 'QP'.")

    # Iterate cleanly through the preferred solvers list
    for solver_name in SOLVER_PREFERENCE[lookup_type]:
        try:
            solver = SolverFactory(solver_name)

            # Gurobi & CPLEX need exception_flag=True to catch license errors instantly
            is_commercial = solver_name in ["gurobi", "cplex"]

            if solver.available(exception_flag=is_commercial):
                logger.info(
                    f"Successfully selected solver: '{solver_name}' for {lookup_type}."
                )
                return solver

        except Exception as e:
            logger.debug(f"Solver '{solver_name}' not available or unlicensed: {e}")
            continue

    raise RuntimeError(
        f"No valid {lookup_type} solvers from "
        f"{SOLVER_PREFERENCE[lookup_type]} "
        f"are installed and licensed."
    )
