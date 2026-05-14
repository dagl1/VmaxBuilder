from functools import partial
from typing import Iterable, Optional

from cobrapy_fork.core.dictlist import DictList
from cobrapy_fork.core.model import Model, logger
from cobrapy_fork.core.object import Object
from cobrapy_fork.core.reaction import Reaction
from cobrapy_fork.util.context import get_context


def add_reactions_slim(self, reaction_list: Iterable[Reaction]) -> None:
    """Add reactions to the model.

    Reactions with identifiers identical to a reaction already in the
    model are ignored.

    The change is reverted upon exit when using the model as a context.

    Parameters
    ----------
    reaction_list : list
        A list of `.cobrapy_fork.Reaction` objects
    """

    def existing_filter(rxn: Reaction) -> bool:
        """Check if the reaction does not exists in the model.

        Parameters
        ----------
        rxn: .cobrapy_fork.Reaction

        Returns
        -------
        bool
            False if reaction exists, True if it doesn't.
            If the reaction exists, will log a warning.
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
            context(partial(setattr, reaction, "_model", None))
        # Build a `list()` because the dict will be modified in the loop.
        for metabolite in list(reaction.metabolites):
            # TODO: Maybe this can happen with
            #  Reaction.add_metabolites(combine=False)
            # TODO: Should we add a copy of the metabolite instead?
            if metabolite not in self.metabolites:
                self.add_metabolites(metabolite)
            # A copy of the metabolite exists in the model, the reaction
            # needs to point to the metabolite in the model.
            else:
                # FIXME: Modifying 'private' attributes is horrible.
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

    # from cameo ...
    print(f"Added {len(pruned)} reactions to the model '{self.id}' ({self.name}).")
    #### turned of for slim version by Jelle Bonthuis MaCSBio, 2025-06-20
    ### should lead to a performance increase
    # if self.solver is not None:
    #     self._populate_solver(pruned)


Model.add_reactions_slim = add_reactions_slim
