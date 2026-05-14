from functools import partial
from typing import Any, Callable, Iterable, Optional, Sequence, Tuple, Union

from cobrapy_fork.core.dictlist import DictList
from cobrapy_fork.core.model import Model, logger
from cobrapy_fork.core.object import Object
from cobrapy_fork.core.reaction import Reaction
from cobrapy_fork.util.context import get_context, resettable


def update_variable_bounds_slim(self) -> None:
    """Update the forward_variable and reverse_variable bounds.

    Sets the forward_variable and reverse_variable bounds based on lower and
    upper bounds. This function is slim because it does not do anything to the
    underlying optlang interface.

    Added by Jelle Bonthuis, 2025-06-20 for VmaxBuilder to improve performance.
    """
    if self.model is None:
        return


bounds = Reaction.bounds


@bounds.setter
@resettable
def bounds(
    self,
    value: Union[Tuple[float, float, bool], Tuple[float, float], Sequence[float]],
) -> None:
    """Set the bounds directly, using a tuple or list.

    Parameters
    ----------
    value: tuple or sequence
        The lower bound and upper bound. Invalid bounds will raise ValueError.

    When using a `HistoryManager` context, this attribute can be set
    temporarily, reversed when the exiting the context.

    Raises
    ------
    ValueError
        If lower bound higher than upper bound, via _check_bounds.

    """
    if isinstance(value, tuple) and len(value) == 3:
        lower, upper, is_slim = value
    else:
        lower, upper = value
        is_slim = False

    # Validate bounds before setting them.
    self._check_bounds(lower, upper)
    self._lower_bound = lower
    self._upper_bound = upper
    if not is_slim:
        self.update_variable_bounds()
    # else:
    #     self.update_variable_bounds_slim()


def _set_id_with_model_slim(self, value: str) -> None:
    """Set Reaction id in model, check that it doesn't already exist.

    The function will rebuild the model reaction index.

    Parameters
    ----------
    value: str
        A string that represents the id.

    Raises
    ------
    ValueError
        If the model already contains a reaction with the id value.
    """
    if value in self.model.reactions:
        raise ValueError(f"The model already contains a reaction with the id: {value}")
    # forward_variable = self.forward_variable
    # reverse_variable = self.reverse_variable
    self._id = value
    # self.model.reactions._generate_index()
    # forward_variable.name = self.id
    # reverse_variable.name = self.reverse_id


Reaction.bounds = bounds
Reaction.update_variable_bounds_slim = update_variable_bounds_slim
