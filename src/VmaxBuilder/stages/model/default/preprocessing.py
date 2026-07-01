"""Generated: validation needed.
Description:
    Model preprocessing functions for reversible-to-irreversible model conversion.
    Pipeline always produces a closed irreversible model with boundary reactions
    zeroed and reversible reactions split into forward/backward pairs.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from enum import Enum
from time import perf_counter
from typing import TYPE_CHECKING, Any, TypedDict, cast

from cobra import Model, Reaction
from cobra.util.context import resettable
from pandas import DataFrame
from typing_extensions import Protocol

from VmaxBuilder.base.configs import FullConfig
from VmaxBuilder.stages.model.default.implementation import TranscriptMetadataServiceProtocol

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
    Modifies:
        self._id: updated without triggering per-rename model index rebuild.
    """

    self._id = value


@contextmanager
def _temporary_fast_reaction_patches() -> Iterator[None]:
    """Generated: validation needed.
    Description:
        Temporarily patch `cobra.Reaction` internals used by FAST irreversible split.
        Adds 3-tuple slim bounds support and no-op ID model index hook, then restores
        original methods on exit even when an exception is raised.
    Yields:
        None: Active patch scope.
    Modifies:
        `cobra.Reaction.bounds` and `cobra.Reaction._set_id_with_model` for context scope.
    """

    original_set_id_with_model = Reaction._set_id_with_model  # type: ignore[attr-defined]
    original_bounds_property = Reaction.bounds

    @original_bounds_property.setter
    @resettable  # ty: ignore[invalid-argument-type]
    def patched_bounds(
        self: Reaction,
        value: tuple[float, float, bool] | tuple[float, float] | Sequence[float],
    ) -> None:
        if isinstance(value, tuple) and len(value) == 3:
            lower_bound, upper_bound, is_slim = value
        else:
            lower_bound, upper_bound = value
            is_slim = False

        self._check_bounds(lower_bound, upper_bound)
        self._lower_bound = lower_bound
        self._upper_bound = upper_bound
        if not is_slim:
            self.update_variable_bounds()

    reaction_class = cast(Any, Reaction)
    try:
        reaction_class._set_id_with_model = _set_id_with_model_slim
        reaction_class.bounds = patched_bounds
        yield
    finally:
        reaction_class._set_id_with_model = original_set_id_with_model
        reaction_class.bounds = original_bounds_property


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
        Applies temporary `Reaction` monkeypatches only inside a safe context.
    Args:
        irreversible_model (cobra.Model): Model containing the reversible reactions
            (already copied from the source model).
        additional_reactions (dict[cobra.Reaction, cobra.Reaction]): Mapping from
            forward reaction (already in model) to its backward copy.
    Returns:
        tuple[cobra.Model, list[list[int]]]: Updated model and rev2irrev mapping.
            rev2irrev[i] is a list of 1-based reaction indices for the i-th reaction.
    Modifies:
        irreversible_model: reaction IDs, bounds, stoichiometry, and solver rebuilt.
    """
    with _temporary_fast_reaction_patches():
        for forward_reaction, backward_reaction in additional_reactions.items():
            forward_reaction.id = forward_reaction.id + _FORWARD_SUFFIX
            backward_reaction.id = backward_reaction.id + _BACKWARD_SUFFIX

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
    irreversible_model._populate_solver(list(irreversible_model.reactions))  # type: ignore[attr-defined]
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
          and context-scoped slim bounds setter.
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
    mode: IrreversibleModelMode = IrreversibleModelMode.FAST,
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


def _build_transcript_artifacts_for_model(
    model: Model,
    config: FullConfig,
    translation_service: TranscriptMetadataServiceProtocol,
) -> dict[str, Any]:
    """Generated: validation needed.

    Description:
        Build transcript metadata artifacts for model genes when transcript
        target level is requested.

    Args:
        model (Model): Irreversible cobra model.

    Returns:
        dict[str, Any]: Transcript metadata and mapping artifacts.
    """

    genes_in_model = [gene.id for gene in model.genes]
    model_id_type = _build_id_type_name(config.model.id_type, config.model.level)
    if model_id_type is None:
        transcript_df = DataFrame(
            columns=[
                "transcript_id",
                "gene_id",
                "is_protein_coding",
                "is_canonical",
                "peptide_len",
                "cdna_len",
                "peptide_seq",
                "cdna_seq",
            ]
        )
    else:
        transcript_df = translation_service.build_gene_transcript_dataframe(
            genes_in_model,
            gene_id_type=model_id_type,
            species=config.transcripts.id_translation_species,
            provider=config.transcripts.id_translation_provider,
            max_workers=config.transcripts.id_translation_max_workers,
            batch_size=config.transcripts.id_translation_batch_size,
        )

    transcript_to_gene_mapping = transcript_df.set_index("transcript_id")["gene_id"].to_dict()
    gene_to_transcript_mapping = (
        transcript_df.groupby("gene_id")["transcript_id"].agg(list).to_dict()
        if not transcript_df.empty
        else {}
    )
    protein_coding_transcripts = transcript_df[transcript_df["is_protein_coding"]][
        "transcript_id"
    ].tolist()
    canonical_transcripts = transcript_df[transcript_df["is_canonical"]][
        "transcript_id"
    ].tolist()
    transcript_sequences = transcript_df[
        [
            "transcript_id",
            "gene_id",
            "peptide_len",
            "cdna_len",
            "peptide_seq",
            "cdna_seq",
        ]
    ]

    return {
        "gene_transcript_mapping": transcript_df,
        "transcript_to_gene_mapping": transcript_to_gene_mapping,
        "gene_to_transcript_mapping": gene_to_transcript_mapping,
        "protein_coding_transcripts": protein_coding_transcripts,
        "canonical_transcripts": canonical_transcripts,
        "transcript_sequences": transcript_sequences,
        "genes_in_model": genes_in_model,
    }


@staticmethod
def _build_id_type_name(provider: str | None, level: str) -> str | None:
    """Generated: validation needed.

    Description:
        Build full identifier type name from provider and granularity level.

    Args:
        provider (str | None): Identifier provider value.
        level (str): Gene/transcript level.

    Returns:
        str | None: Full identifier type name or None when provider missing.
    """

    if provider is None:
        return None
    level_lower = level.lower()
    if provider == "ensembl":
        return f"ensembl_{level_lower}_id"
    return provider
