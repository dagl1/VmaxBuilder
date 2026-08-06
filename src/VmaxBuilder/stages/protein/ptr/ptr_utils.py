from typing import Any

from cobra import Model

from VmaxBuilder.base.configs import FullConfig
from VmaxBuilder.utils.extra_utils import (
    _deduplicate_preserve_order,
    get_transport_reaction_gene_ids,
)


def resolve_gene_or_reaction_group_members(
    model: Model,
    identifiers: list[str],
    expression_gene_ids: set[str] | None = None,
) -> list[str]:
    """Generated: validation needed.

    Description:
        Expand a mixed list of gene IDs and reaction IDs into gene IDs.
        Reaction IDs contribute all associated gene IDs. Gene IDs are passed
        through unchanged.

    Args:
        model (Any | None): Cobra-like model with ``reactions`` collection.
        identifiers (list[str]): Gene or reaction identifiers.
        expression_gene_ids (set[str] | None): Optional filter restricting
            returned genes to those present in expression data.

    Returns:
        list[str]: Ordered unique gene IDs.
    """
    if model is None:
        resolved_gene_ids = identifiers
    else:
        reaction_lookup: dict[str, Any] = {
            str(reaction.id): reaction for reaction in model.reactions
        }
        resolved_gene_ids = []
        for identifier in identifiers:
            reaction = reaction_lookup.get(identifier)
            if reaction is None:
                resolved_gene_ids.append(identifier)
                continue
            resolved_gene_ids.extend(str(gene.id) for gene in reaction.genes)

    if expression_gene_ids is not None:
        resolved_gene_ids = [
            gene_id for gene_id in resolved_gene_ids if gene_id in expression_gene_ids
        ]
    return _deduplicate_preserve_order(resolved_gene_ids)


def resolve_special_gene_groups(
    config: FullConfig,
    cobra_model: Model,
    expression_gene_ids: set[str] | None = None,
) -> dict[str, list[str]]:
    """Generated: validation needed.

    Description:
        Resolve user-provided special gene groups used by PTR unobserved-gene
        imputation. This endpoint enables independent group-wise imputation
        (e.g., transport genes or other custom partitions). Group values
        may contain gene IDs or reaction IDs; ``transport_reactions`` with
        an empty list auto-resolves transport-associated genes from model.

    Args:
        model_artifact (Any | None): Optional cobra-like model used for
            shorthand and reaction-based group expansion.
        expression_gene_ids (set[str] | None): Optional expression-gene
            universe used to filter resolved group members.

    Returns:
        dict[str, list[str]]: Mapping of group name to normalized gene IDs.

    Raises:
        ValueError: When ``transport_reactions`` shorthand is requested
            without a model artifact.
    """
    raw_groups = config.protein.PTR_special_gene_groups
    if raw_groups is None:
        return {}
    normalized_groups: dict[str, list[str]] = {}
    for group_name, group_genes in raw_groups.items():
        normalized_name = str(group_name).strip()
        if normalized_name == "":
            continue
        normalized_entries = [
            str(group_entry).strip()
            for group_entry in group_genes
            if str(group_entry).strip() != ""
        ]
        if normalized_name == "transport_reactions" and not normalized_entries:
            (
                active_transport_reaction_gene_ids,
                passive_transport_reaction_gene_ids,
                non_transport_reaction_gene_ids,
            ) = get_transport_reaction_gene_ids(
                cobra_model,
                expression_gene_ids=expression_gene_ids,
            )
            normalized_groups[normalized_name] = list(
                set(active_transport_reaction_gene_ids).union(
                    set(passive_transport_reaction_gene_ids)
                )
            )
            continue
        normalized_groups[normalized_name] = resolve_gene_or_reaction_group_members(
            cobra_model,
            normalized_entries,
            expression_gene_ids=expression_gene_ids,
        )
    return normalized_groups


def _normalize_sample_label(value: Any) -> str:
    """Generated: validation needed.

    Description:
        Normalize sample/tissue labels for robust matching across expression,
        PTR, and explicit tissue-map configuration.

    Args:
        value (Any): Raw label value.

    Returns:
        str: Normalized label (trimmed, lower-case, optional ``_ptr`` suffix removed).
    """
    text = str(value).strip().lower()
    if text.endswith("_ptr"):
        text = text[: -len("_ptr")]
    return text


def is_valid_int(val):
    try:
        return float(val).is_integer()
    except (ValueError, TypeError):
        return False
