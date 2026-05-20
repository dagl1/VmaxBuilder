"""Cobrapy Model method overrides and enhancements.

This module patches cobra Model methods to:
- Add performance-optimised add_reactions_slim() that skips solver updates
- Provide populate_solver_from_model() to retroactively populate solver
  (critical for models created without initial solver)
- Ensure models work with any solver, not just the initial one

**Key enhancements:**
- add_reactions_slim: Skip solver population during bulk add (performance)
- populate_solver_from_model: Populate solver for reactions not yet in solver
- Works with any cobra-compatible solver (Gurobi, CPLEX, GLPK, etc.)

**Use case:**
When creating large models for performance (no solver initially), use
populate_solver_from_model() before optimisation to ensure solver is ready.

Author: Jelle Bonthuis (MaCSBio)
"""

from functools import partial
from typing import Any, Callable, Iterable, Optional, cast

from cobra.core.dictlist import DictList
from cobra.core.model import Model, logger
from cobra.core.object import Object
from cobra.core.reaction import Reaction
from cobra.util.context import get_context


def add_reactions_slim(self, reaction_list: Iterable[Reaction]) -> None:
    """Generated: validation needed

    Add reactions to model without updating solver (performance optimisation).

    Skips solver population for bulk reactions to avoid bottleneck during
    large model construction. **Use populate_solver_from_model() before
    optimisation** to populate the solver.

    Ignores duplicate IDs. Handles metabolites: links existing mets, adds new ones.
    Updates GPR rules and genes automatically.

    Args:
        reaction_list (Iterable[cobra.Reaction]): List of reactions to add.

    Returns:
        None

    Raises:
        None

    Requires:
        self (Model) must be valid cobrapy Model instance.

    Modifies:
        - self.reactions: adds all non-duplicate reactions
        - self.metabolites: adds new metabolites from reaction stoichiometry
        - self.genes: updates from GPR rules in reactions

    Warning:
        Solver NOT populated. Call populate_solver_from_model() before optimisation.

    See Also:
        populate_solver_from_model: Populate solver after slim add
        cobrapy_fork.Model.add_reactions: Standard (solver-updating) add

    Example:
        >>> model = Model('slim_model')
        >>> model.add_reactions_slim(reactions)  # Fast, no solver overhead
        >>> model.populate_solver_from_model()  # Prepare for optimisation
        >>> solution = model.optimize()
    """

    def existing_filter(rxn: Reaction) -> bool:
        """Check if reaction does not exist in model.

        Args:
            rxn (cobra.Reaction): Reaction to check.

        Returns:
            bool: False if exists (logs warning), True if new.
        """
        if rxn.id in self.reactions:
            logger.warning(f"Ignoring reaction '{rxn.id}' since it already exists.")
            return False
        return True

    # First check whether the reactions exist in the model.
    pruned = DictList(filter(existing_filter, reaction_list))

    context = get_context(self)

    # Add reactions. Also take care of genes and metabolites in the loop.
    for reaction in pruned:
        reaction._model = self
        if context:
            context(cast(Callable[[Any], Any], partial(setattr, reaction, "_model", None)))
        # Build a `list()` because the dict will be modified in the loop.
        for metabolite in list(reaction.metabolites):
            if metabolite not in self.metabolites:
                self.add_metabolites(metabolite)
            # A copy of the metabolite exists in the model, the reaction
            # needs to point to the metabolite in the model.
            else:
                stoichiometry = reaction._metabolites.pop(metabolite)
                model_metabolite = self.metabolites.get_by_id(metabolite.id)
                reaction._metabolites[model_metabolite] = stoichiometry
                model_metabolite._reaction.add(reaction)
                if context:
                    context(partial(model_metabolite._reaction.remove, reaction))
        reaction.update_genes_from_gpr()

    self.reactions += pruned

    if context:
        context(partial(self.reactions.__isub__, pruned))

    logger.info(
        f"Added {len(pruned)} reactions to model '{self.id}' ({self.name}). "
        f"Solver not populated (call populate_solver_from_model() before optimise)."
    )


def populate_solver_from_model(self) -> None:
    """Generated: validation needed

    Populate solver with all model reactions and metabolites.

    **Critical for models created without solver.** Adds all reactions/genes to
    solver's optlang problem. Safe to call multiple times (skips already-added
    reactions). Ensures model works with any solver.

    Args:
        self (cobra.Model): Model instance to populate solver for.

    Returns:
        None

    Raises:
        None (silently skips if no solver set)

    Requires:
        self.solver must be set and compatible with cobrapy

    Modifies:
        self.solver: adds all reactions/metabolites/genes to optlang problem

    Example:
        >>> model = Model('example', problem=None)  # No solver
        >>> model.add_reactions_slim(reactions)
        >>> model.solver = optlang_gurobi_interface.Model()  # Set solver
        >>> model.populate_solver_from_model()  # Populate
        >>> model.optimize()
        <Solution ...>
    """
    if self.solver is None:
        logger.warning("No solver attached. Skipping populate_solver_from_model().")
        return

    # Populate solver with all reactions, genes, and metabolites
    self._populate_solver(list(self.reactions))
    logger.info(f"Populated solver for model '{self.id}' ({len(self.reactions)} reactions).")


model_class_with_extensions = cast(Any, Model)
model_class_with_extensions.add_reactions_slim = add_reactions_slim
model_class_with_extensions.populate_solver_from_model = populate_solver_from_model
