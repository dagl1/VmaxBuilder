"""Generated: validation needed.
Description:
    Model preprocessing functions for reversible-to-irreversible model conversion.
    Pipeline always produces a closed irreversible model with boundary reactions
    zeroed and reversible reactions split into forward/backward pairs.
"""

from __future__ import annotations

import logging
from enum import Enum
from time import perf_counter
from typing import TYPE_CHECKING, TypedDict

from cobra import Model, Reaction

if TYPE_CHECKING:
    from VmaxBuilder.config.dataclasses import ModelConfig
logger = logging.getLogger(__name__)
_FORWARD_SUFFIX = "_f"
_BACKWARD_SUFFIX = "_r"


class IrreversibleModelMode(str, Enum):
    """Generated: validation needed.
    Description:
        Strategy for splitting reversible reactions into irreversible forward/backward pairs.
        - SAFE: Standard cobrapy methods, index rebuilt after each rename.
        - FAST: Batch rename with temporary no-op ID hook, single rebuild, slim bound setter.
    """

    SAFE = "safe"
    FAST = "fast"


class ModelPreprocessingResult(TypedDict):
    """Generated: validation needed.
    Description:
        Output container for model preprocessing stage. Holds the closed irreversible
        model and the index mapping used downstream.
    Args:
        irreversible_model (cobra.Model): Closed irreversible cobra model
            (boundary reactions zeroed, reversible reactions split into _f/_r pairs).
        rev2irrev (list[list[int]]): Mapping from original reaction index (1-based)
            to one or two irreversible reaction indices.
    """

    irreversible_model: Model
    rev2irrev: list[list[int]]


def _set_id_with_model_slim(self: Reaction, value: str) -> None:
    """Generated: validation needed.
    Description:
        No-op slim replacement for Reaction._set_id_with_model. Skips model
        index rebuild during bulk ID reassignment. Caller must call
        model.reactions._generate_index() afterwards to restore consistency.
    Args:
        self (cobra.Reaction): Reaction instance (implicit, monkey-patched).
        value (str): New reaction identifier.
    Requires:
        Caller must rebuild index: model.reactions._generate_index()
    """


def _split_reversible_reactions_safe(
    irreversible_model: Model,
    additional_reactions: dict[Reaction, Reaction],
) -> tuple[Model, list[list[int]]]:
    """Generated: validation needed.
    Description:
        Safe variant of reversible-to-irreversible splitting. Renames forward/
        backward reaction pairs, adds backward reactions to the model, then
        adjusts bounds and metabolite coefficients. Uses standard cobrapy methods
        throughout, which rebuilds the index on every ID rename.
    Args:
        irreversible_model (cobra.Model): Model containing the reversible reactions
            (already copied from the source model).
        additional_reactions (dict[cobra.Reaction, cobra.Reaction]): Mapping from
            forward reaction (already in model) to its backward copy.
    Returns:
        tuple[cobra.Model, list[list[int]]]: Updated model and rev2irrev mapping.
            rev2irrev[i] is a list of 1-based reaction indices for the i-th reaction.
    Modifies:
        irreversible_model: reaction IDs, bounds, and stoichiometry updated in-place.
    """
    original_reaction_count = len(irreversible_model.reactions)
    indices_by_id: dict[str, int] = {
        reaction.id: idx for idx, reaction in enumerate(irreversible_model.reactions)
    }
    rev2irrev: list[list[int]] = [[idx + 1] for idx in range(original_reaction_count)]
    for backward_reaction_idx, (forward_reaction, backward_reaction) in enumerate(
        additional_reactions.items()
    ):
        original_id = forward_reaction.id
        forward_reaction.id = forward_reaction.id + _FORWARD_SUFFIX
        backward_reaction.id = backward_reaction.id + _BACKWARD_SUFFIX
        forward_reaction_idx = indices_by_id[original_id]
        rev2irrev[forward_reaction_idx].append(
            backward_reaction_idx + 1 + original_reaction_count
        )
    irreversible_model.add_reactions(list(additional_reactions.values()))
    start = perf_counter()
    for forward_reaction, backward_reaction in additional_reactions.items():
        backward_reaction.bounds = (0.0, -forward_reaction.lower_bound)
        backward_reaction.add_metabolites(
            {met: -1 * coeff for met, coeff in forward_reaction.metabolites.items()},
            combine=False,
            reversibly=False,
        )
        forward_reaction.bounds = (0.0, forward_reaction.upper_bound)
    logger.debug("Safe split: bound/metabolite update took %.2fs.", perf_counter() - start)
    return irreversible_model, rev2irrev


def _split_reversible_reactions_fast(
    irreversible_model: Model,
    additional_reactions: dict[Reaction, Reaction],
) -> tuple[Model, list[list[int]]]:
    """Generated: validation needed.
    Description:
        Fast variant of reversible-to-irreversible splitting. Temporarily patches
        Reaction._set_id_with_model to skip per-ID index rebuilds, renames all
        reactions in bulk, then restores the method and calls _generate_index once.
        Finishes by rebuilding the solver from scratch.
        Use only when model will undergo full solver rebuild immediately after.
        Requires cobrapy_overwrites.cobrapy_reaction import to be active for slim
        bound sets (3-tuple syntax).
    Args:
        irreversible_model (cobra.Model): Model containing the reversible reactions
            (already copied from the source model).
        additional_reactions (dict[cobra.Reaction, cobra.Reaction]): Mapping from
            forward reaction (already in model) to its backward copy.
    Returns:
        tuple[cobra.Model, list[list[int]]]: Updated model and rev2irrev mapping.
            rev2irrev[i] is a list of 1-based reaction indices for the i-th reaction.
    Requires:
        cobrapy_overwrites.cobrapy_reaction must be imported to enable slim bounds setter.
    Modifies:
        irreversible_model: reaction IDs, bounds, stoichiometry, and solver rebuilt.
    """
    original_set_id_with_model = Reaction._set_id_with_model  # type: ignore[attr-defined]
    Reaction._set_id_with_model = _set_id_with_model_slim  # type: ignore[attr-defined]
    for forward_reaction, backward_reaction in additional_reactions.items():
        forward_reaction.id = forward_reaction.id + _FORWARD_SUFFIX
        backward_reaction.id = backward_reaction.id + _BACKWARD_SUFFIX
    Reaction._set_id_with_model = original_set_id_with_model  # type: ignore[attr-defined]
    irreversible_model.reactions._generate_index()
    original_reaction_count = len(irreversible_model.reactions)
    indices_by_id: dict[str, int] = {
        reaction.id: idx for idx, reaction in enumerate(irreversible_model.reactions)
    }
    rev2irrev: list[list[int]] = [[idx + 1] for idx in range(original_reaction_count)]
    for backward_reaction_idx, (forward_reaction, _) in enumerate(
        additional_reactions.items()
    ):
        forward_reaction_idx = indices_by_id[forward_reaction.id]
        rev2irrev[forward_reaction_idx].append(
            backward_reaction_idx + 1 + original_reaction_count
        )
    add_start = perf_counter()
    irreversible_model.add_reactions(list(additional_reactions.values()))
    logger.debug("Fast split: add_reactions took %.2fs.", perf_counter() - add_start)
    bounds_start = perf_counter()
    for forward_reaction, backward_reaction in additional_reactions.items():
        backward_reaction.bounds = (0.0, -forward_reaction.lower_bound, True)  # type: ignore[assignment]
        backward_reaction.add_metabolites(
            {met: -1 * coeff for met, coeff in forward_reaction.metabolites.items()},
            combine=False,
            reversibly=False,
        )
        forward_reaction.bounds = (0.0, forward_reaction.upper_bound, True)  # type: ignore[assignment]
    logger.debug("Fast split: bound update took %.2fs.", perf_counter() - bounds_start)
    solver_start = perf_counter()
    irreversible_model._populate_solver(  # type: ignore[attr-defined]
        list(irreversible_model.reactions),
        list(irreversible_model.metabolites),
    )
    logger.debug("Fast split: solver rebuild took %.2fs.", perf_counter() - solver_start)
    return irreversible_model, rev2irrev


def create_irreversible_model(
    cobra_model: Model,
    mode: IrreversibleModelMode = IrreversibleModelMode.SAFE,
) -> tuple[Model, list[list[int]]]:
    """Generated: validation needed.
    Description:
        Convert a cobra model to irreversible form by splitting every reaction
        with lb < 0 and ub > 0 into forward (_f) and backward (_r) sub-reactions.
        Returns the transformed model and a rev2irrev index mapping.
        Two modes available:
        - SAFE: Standard cobrapy methods, index rebuilt after each rename.
        - FAST: Batch rename with temporary no-op ID hook, single index rebuild,
          slim bound setter. Requires cobrapy_overwrites.cobrapy_reaction active.
    Args:
        cobra_model (cobra.Model): Source model. Will be mutated in-place.
        mode (IrreversibleModelMode): Splitting strategy. Default SAFE.
    Returns:
        tuple[cobra.Model, list[list[int]]]: Irreversible model and rev2irrev mapping.
            rev2irrev[i] contains 1-based indices for the i-th original reaction:
            [forward_idx] for already-irreversible reactions,
            [forward_idx, backward_idx] for split reversible reactions.
    Raises:
        ValueError: When mode is not a valid IrreversibleModelMode.
    Requires:
        When mode is FAST: cobrapy_overwrites.cobrapy_reaction must be imported.
    Modifies:
        cobra_model: reaction IDs, bounds, and stoichiometry updated in-place.
    Example:
        >>> irrev_model, mapping = create_irreversible_model(model)
        >>> all(r.lower_bound >= 0 for r in irrev_model.reactions)
        True
    """
    reversible_reactions: list[Reaction] = [
        reaction
        for reaction in cobra_model.reactions
        if reaction.lower_bound < 0 and reaction.upper_bound > 0
    ]
    reversible_count = len(reversible_reactions)
    if reversible_count == 0:
        logger.warning("Model already irreversible. Returning unchanged.")
        return cobra_model, []
    logger.debug("Found %d reversible reactions to split.", reversible_count)
    additional_reactions: dict[Reaction, Reaction] = {
        reaction: reaction.copy() for reaction in reversible_reactions
    }
    if mode is IrreversibleModelMode.SAFE:
        return _split_reversible_reactions_safe(cobra_model, additional_reactions)
    if mode is IrreversibleModelMode.FAST:
        return _split_reversible_reactions_fast(cobra_model, additional_reactions)
    raise ValueError(
        f"Unknown IrreversibleModelMode: {mode!r}. "
        f"Valid options: {[m.value for m in IrreversibleModelMode]}"
    )


def preprocess_model(
    cobra_model: Model,
    config: ModelConfig,
    mode: IrreversibleModelMode = IrreversibleModelMode.SAFE,
) -> ModelPreprocessingResult:
    """Generated: validation needed.
    Description:
        Preprocess a cobra model into closed irreversible form ready for the
        VmaxBuilder pipeline. Steps in order:
        1. Make a copy if config.make_copy is True.
        2. Close all boundary reactions (bounds set to (0.0, 0.0)).
        3. Split reversible reactions into forward (_f) and backward (_r) pairs.
    Args:
        cobra_model (cobra.Model): Source cobra model.
        config (ModelConfig): Model configuration with make_copy flag.
        mode (IrreversibleModelMode): Splitting strategy. Default SAFE.
    Returns:
        ModelPreprocessingResult: TypedDict with keys:
            - irreversible_model: Closed irreversible cobra model.
            - rev2irrev: Mapping from original to irreversible reaction indices.
    Raises:
        ValueError: Propagated from create_irreversible_model on invalid mode.
    Requires:
        When mode is FAST: cobrapy_overwrites.cobrapy_reaction must be imported.
    Modifies:
        cobra_model (or its copy): boundary reactions closed, reversible reactions split.
    Example:
        >>> from VmaxBuilder.config.dataclasses import ModelConfig
        >>> config = ModelConfig(make_copy=True)
        >>> result = preprocess_model(model, config)
        >>> result["irreversible_model"]
        <Model ...>
        >>> result["rev2irrev"]
        [[1], [2, 5], [3], [4], ...]
    """
    working_model: Model = cobra_model.copy() if config.make_copy else cobra_model
    for reaction in working_model.reactions:
        if reaction.boundary:
            reaction.bounds = (0.0, 0.0)
    irreversible_model, rev2irrev = create_irreversible_model(
        working_model,
        mode=mode,
    )
    return {"irreversible_model": irreversible_model, "rev2irrev": rev2irrev}
