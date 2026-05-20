"""Cobrapy Reaction method overrides and enhancements.

This module patches cobra Reaction methods for performance optimisation:
- update_variable_bounds_slim(): Skip optlang sync when solver not needed
- bounds setter: Support slim mode for bulk bound updates

**Use case:**
When building large models without solver (performance), use slim bounds
mode to avoid optlang overhead. Populate solver before optimisation.

Author: Jelle Bonthuis (MaCSBio)
"""

from functools import partial
from typing import Any, Callable, Iterable, Optional, Sequence, Tuple, Union

from cobra.core.dictlist import DictList
from cobra.core.model import Model, logger
from cobra.core.object import Object
from cobra.core.reaction import Reaction
from cobra.util.context import get_context, resettable


def update_variable_bounds_slim(self) -> None:
    """Generated: validation needed

    Skip bounds update in solver (no-op for slim model mode).

    When model built without solver, calling update_variable_bounds() on
    every reaction is wasteful. This no-op allows slim mode operations
    without solver overhead.

    Args:
        self (cobra.Reaction): Reaction instance (implicit).

    Returns:
        None

    Added by Jelle Bonthuis, 2025-06-20 for VmaxBuilder to improve performance.
    """
    if self.model is None:
        return


bounds = Reaction.bounds


@bounds.setter
@resettable  # ty: ignore[invalid-argument-type]
def bounds(
    self,
    value: Union[Tuple[float, float, bool], Tuple[float, float], Sequence[float]],
) -> None:
    """Generated: validation needed

    Set reaction bounds with optional slim (no solver sync) mode.

    Overrides standard bounds setter to support 3-tuple with slim flag:
    (lower, upper, is_slim). When is_slim=True, skips optlang sync.

    Args:
        value (tuple | Sequence[float]): Either:
            - (lower, upper): standard 2-tuple → normal bounds mode
            - (lower, upper, is_slim): 3-tuple → slim mode if is_slim=True

    Returns:
        None

    Raises:
        ValueError: If bounds invalid (lower > upper) via _check_bounds.

    Requires:
        None

    Modifies:
        - self._lower_bound, self._upper_bound: sets new bounds
        - self optlang variables: updated unless is_slim=True

    Warning:
        Slim mode (is_slim=True) skips optlang sync. Only use during bulk
        model construction without solver.

    Example:
        >>> rxn.bounds = (-10, 20)  # Normal: syncs solver
        >>> rxn.bounds = (-10, 20, True)  # Slim: no solver sync
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


Reaction.bounds = bounds
Reaction.update_variable_bounds_slim = (
    update_variable_bounds_slim  # ty: ignore[unresolved-attribute]
)
