"""Generated: validation needed.

Description:
    Reusable preprocessing utilities for parsing GPR rules into independently
    functioning protein (IFP) complexes.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from itertools import product
from typing import Any

from cobra import Model

_GPR_OPERATOR_PATTERN = re.compile(r"\b(and|or)\b|&&|\|\||[|&]", flags=re.IGNORECASE)
_GPR_TOKEN_PATTERN = re.compile(r"\(|\)|\band\b|\bor\b|[^\s()]+", flags=re.IGNORECASE)
_WHITESPACE_PATTERN = re.compile(r"\s+")
_GPR_AND_SPLIT_PATTERN = re.compile(r"\band\b", flags=re.IGNORECASE)
_GPRNode = str | tuple[str, "_GPRNode", "_GPRNode"]


class TranscriptIFPExpansionOutcome(dict[str, Any]):
    """Generated: validation needed.

    Description:
        Structured outcome of one gene-level IFP transcript expansion attempt.
    """


@dataclass(frozen=True)
class _TokenCursor:
    """Generated: validation needed.

    Description:
        Lightweight cursor for recursive-descent parsing over immutable token tuple.

    Args:
        tokens (tuple[str, ...]): Token stream.
        position (int): Current read index.
    """

    tokens: tuple[str, ...]
    position: int = 0

    def peek(self) -> str | None:
        """Generated: validation needed.

        Description:
            Return next token without consuming it.

        Returns:
            str | None: Next token if available.
        """

        if self.position >= len(self.tokens):
            return None
        return self.tokens[self.position]

    def advance(self) -> tuple[str, _TokenCursor]:
        """Generated: validation needed.

        Description:
            Consume one token and return updated cursor.

        Returns:
            tuple[str, _TokenCursor]: Consumed token and advanced cursor.

        Raises:
            ValueError: When cursor is already at stream end.
        """

        token = self.peek()
        if token is None:
            raise ValueError("Unexpected end of GPR expression.")
        return token, _TokenCursor(tokens=self.tokens, position=self.position + 1)


@lru_cache(maxsize=4096)
def simplify_gpr_rule_cached(gpr_rule: str) -> tuple[tuple[str, ...], ...]:
    """Generated: validation needed.

    Description:
        Parse and expand one GPR rule into unique sorted IFPs.

    Args:
        gpr_rule (str): Raw GPR rule.

    Returns:
        tuple[tuple[str, ...], ...]: Unique `and` IFPs.

    Raises:
        ValueError: When expression is malformed.
    """

    normalised_rule = _normalise_gpr_rule(gpr_rule)
    token_stream = _tokenise_gpr_rule(normalised_rule)
    parsed_tree, cursor = _parse_or_expression(_TokenCursor(tokens=token_stream))
    if cursor.peek() is not None:
        raise ValueError(f"Unexpected trailing token in GPR rule: '{cursor.peek()}'.")
    return _deduplicate_IFPs(_expand_tree_to_gene_IFPs(parsed_tree))


def simplify_gpr_rule(gpr_rule: str) -> list[str]:
    """Generated: validation needed.

    Description:
        Convert one raw GPR rule into textual gene-level IFP expressions.

    Args:
        gpr_rule (str): Raw GPR rule.

    Returns:
        list[str]: Simplified IFP strings.
    """

    return [" and ".join(IFP) for IFP in simplify_gpr_rule_cached(gpr_rule)]


def build_IFP_mapping_from_gpr_rules(
    gpr_rules: dict[str, list[str]],
) -> dict[str, dict[str, Any]]:
    """Generated: validation needed.

    Description:
        Build per-rule IFP payloads from unique GPR rules.

    Args:
        gpr_rules (set[str]): Unique GPR rules.

    Returns:
        dict[str, dict[str, Any]]: Per-rule payload with simplified IFPs and counts.
    """

    # todo: change IFP mapping to be: rule -> {IFPs, reactions, genes}
    IFP_mapping: dict[str, dict[str, Any]] = {}
    for gpr_rule in sorted(gpr_rules):
        simplified_gene_IFPs = simplify_gpr_rule(gpr_rule)
        IFP_payloads: list[dict[str, Any]] = []
        for IFP in simplified_gene_IFPs:
            IFP_payload = {
                "IFP": IFP,
                "reactions_with_IFP": gpr_rules[gpr_rule],
                "genes_in_IFP": sorted(set(token for token in IFP.split(" and "))),
            }
            IFP_payloads.append(IFP_payload)
        genes = sorted(
            set(token for IFP in simplified_gene_IFPs for token in IFP.split(" and "))
        )
        _expansion_count = calculate_IFP_expansion_count(
            [tuple(token.split(" and ")) for token in simplified_gene_IFPs]
        )
        reactions = gpr_rules[gpr_rule]
        IFP_mapping[gpr_rule] = {
            "IFP_objects": IFP_payloads,
            # "expansion_count": expansion_count,
            "n_IFPs_in_GPR_rule": len(simplified_gene_IFPs),
            "reactions_with_GPR_rule": reactions,
            "genes_in_GPR_rule": genes,
        }
    return IFP_mapping


def build_gene_to_transcripts_mapping(
    mapping_artifact: Any,
) -> dict[str, tuple[str, ...]]:
    """Generated: validation needed.

    Description:
        Build canonical gene->transcript mapping from scaffold artifacts.

    Args:
        mapping_artifact (Any): Either `dict[gene_id, transcripts]` or dataframe-like
            object with `gene_id` and `transcript_id` columns.

    Returns:
        dict[str, tuple[str, ...]]: Canonical mapping where each transcript list is
            sorted and deduplicated.
    """

    gene_to_transcripts: dict[str, set[str]] = {}

    if isinstance(mapping_artifact, Mapping):
        _collect_transcripts_from_mapping(mapping_artifact, gene_to_transcripts)
    elif hasattr(mapping_artifact, "__getitem__") and hasattr(mapping_artifact, "columns"):
        _collect_transcripts_from_dataframe_like(mapping_artifact, gene_to_transcripts)

    return {
        gene_id: tuple(sorted(transcript_ids))
        for gene_id, transcript_ids in gene_to_transcripts.items()
        if transcript_ids
    }


def get_unique_gpr_rules(cobra_model: Model) -> dict[str, list[str]]:
    """Generated: validation needed.

    Description:
        Extract unique non-empty GPR rules from the model.

    Args:
        cobra_model (Model): COBRApy model object.

    Returns:
        set[str]: Unique GPR rules.
    """

    if cobra_model is None:
        raise ValueError("Cobra model not found in scaffold artifacts.")

    gpr_rules: dict[str, list[str]] = {}
    for reaction in cobra_model.reactions:
        rule = reaction.gene_reaction_rule.strip()
        if rule:
            gpr_rules.setdefault(rule, []).append(reaction.id)

    return gpr_rules


def _collect_transcripts_from_mapping(
    mapping_artifact: Mapping[Any, Any],
    gene_to_transcripts: dict[str, set[str]],
) -> None:
    """Generated: validation needed.

    Description:
        Merge dict-like mapping artifact entries into canonical gene->transcript store.

    Args:
        mapping_artifact (Mapping[Any, Any]): Dict-like gene->transcript mapping.
        gene_to_transcripts (dict[str, set[str]]): Mutable accumulator.

    Modifies:
        gene_to_transcripts dictionary.
    """

    for gene_id, transcript_values in mapping_artifact.items():
        gene_key = str(gene_id)
        if isinstance(transcript_values, str):
            transcript_list = [transcript_values]
        elif isinstance(transcript_values, Sequence):
            transcript_list = [str(transcript_id) for transcript_id in transcript_values]
        else:
            transcript_list = [str(transcript_values)]

        for transcript_id in transcript_list:
            if transcript_id:
                gene_to_transcripts.setdefault(gene_key, set()).add(transcript_id)


def _collect_transcripts_from_dataframe_like(
    mapping_artifact: Any,
    gene_to_transcripts: dict[str, set[str]],
) -> None:
    """Generated: validation needed.

    Description:
        Merge dataframe-like transcript mapping rows into canonical gene->transcript store.

    Args:
        mapping_artifact (Any): Dataframe-like object containing gene/transcript columns.
        gene_to_transcripts (dict[str, set[str]]): Mutable accumulator.

    Modifies:
        gene_to_transcripts dictionary.
    """

    columns = set(mapping_artifact.columns)
    if not {"gene_id", "transcript_id"}.issubset(columns):
        return

    for _, row in mapping_artifact[["gene_id", "transcript_id"]].iterrows():
        gene_id = str(row["gene_id"])
        transcript_id = str(row["transcript_id"])
        if gene_id and transcript_id:
            gene_to_transcripts.setdefault(gene_id, set()).add(transcript_id)


def expand_gene_IFP_to_transcript_IFPs(
    gene_IFP: str,
    gene_to_transcripts: Mapping[str, Sequence[str]],
    *,
    maximum_expansion: int,
) -> TranscriptIFPExpansionOutcome:
    """Generated: validation needed.

    Description:
        Expand one gene-level IFP into transcript-level IFPs using gene mappings.

    Args:
        gene_IFP (str): Gene-level IFP string joined by `and`.
        gene_to_transcripts (Mapping[str, Sequence[str]]): Gene->transcript mapping.
        maximum_expansion (int): Maximum allowed expansion count.

    Returns:
        TranscriptIFPExpansionOutcome: Structured expansion result including
            transcript IFPs, expansion count, threshold flag, and transcript choices.
    """

    gene_tokens = [
        gene_token.strip()
        for gene_token in _GPR_AND_SPLIT_PATTERN.split(gene_IFP)
        if gene_token.strip()
    ]
    if not gene_tokens:
        return TranscriptIFPExpansionOutcome(
            transcript_IFPs=[],
            expansion_count=0,
            exceeded_threshold=False,
            transcripts_used_by_gene={},
        )

    transcript_choices: list[tuple[str, ...]] = []
    transcripts_used_by_gene: dict[str, tuple[str, ...]] = {}
    for gene_token in gene_tokens:
        mapped_transcripts = gene_to_transcripts.get(gene_token)
        if mapped_transcripts:
            transcript_group = tuple(
                str(transcript_id) for transcript_id in mapped_transcripts
            )
        else:
            # Keep unmapped gene token as fallback to avoid data loss.
            transcript_group = (gene_token,)

        transcript_choices.append(transcript_group)
        transcripts_used_by_gene[gene_token] = transcript_group

    expansion_count = calculate_IFP_expansion_count(transcript_choices)
    if expansion_count > maximum_expansion:
        return TranscriptIFPExpansionOutcome(
            transcript_IFPs=[],
            expansion_count=expansion_count,
            exceeded_threshold=True,
            transcripts_used_by_gene=transcripts_used_by_gene,
        )

    transcript_IFPs = {
        " and ".join(transcript_tuple) for transcript_tuple in product(*transcript_choices)
    }
    return TranscriptIFPExpansionOutcome(
        transcript_IFPs=sorted(transcript_IFPs),
        expansion_count=expansion_count,
        exceeded_threshold=False,
        transcripts_used_by_gene=transcripts_used_by_gene,
    )


def calculate_IFP_expansion_count(transcript_choices: Sequence[Sequence[str]]) -> int:
    """Generated: validation needed.

    Description:
        Calculate transcript expansion count for one gene-level IFP.

    Args:
        transcript_choices (Sequence[Sequence[str]]): Replacement options per gene token.

    Returns:
        int: Expansion count (`AND` product of replacement counts).
    """

    expansion_count = 1
    for choice_group in transcript_choices:
        expansion_count *= max(len(choice_group), 1)
    return expansion_count


def clear_simplification_cache() -> None:
    """Generated: validation needed.

    Description:
        Clear simplification cache for deterministic benchmarks.
    """

    simplify_gpr_rule_cached.cache_clear()


def get_simplification_cache_info() -> dict[str, int]:
    """Generated: validation needed.

    Description:
        Return simplification cache statistics.

    Returns:
        dict[str, int]: Cache statistics dictionary.
    """

    cache_info = simplify_gpr_rule_cached.cache_info()
    return {
        "hits": cache_info.hits,
        "misses": cache_info.misses,
        "maxsize": cache_info.maxsize or 0,
        "currsize": cache_info.currsize,
    }


def _normalise_gpr_rule(gpr_rule: str) -> str:
    """Generated: validation needed.

    Description:
        Canonicalise mixed symbolic/text GPR operators into lowercase words.

    Args:
        gpr_rule (str): Raw GPR rule.

    Returns:
        str: Normalized GPR string.
    """

    stripped_rule = gpr_rule.strip().replace("∨", " or ").replace("∧", " and ")
    if not stripped_rule:
        raise ValueError("GPR rule is empty.")

    def _replace_operator(match: re.Match[str]) -> str:
        matched_token = match.group(0).lower()
        if matched_token in {"or", "|", "||"}:
            return " or "
        return " and "

    normalised_rule = _GPR_OPERATOR_PATTERN.sub(_replace_operator, stripped_rule)
    normalised_rule = normalised_rule.replace("(", " ( ").replace(")", " ) ")
    return _WHITESPACE_PATTERN.sub(" ", normalised_rule).strip()


def _tokenise_gpr_rule(normalised_gpr_rule: str) -> tuple[str, ...]:
    """Generated: validation needed.

    Description:
        Tokenize normalized GPR text into operators, parentheses, and gene symbols.

    Args:
        normalised_gpr_rule (str): Canonicalized GPR rule.

    Returns:
        tuple[str, ...]: Ordered token stream.
    """

    tokens = [
        token.strip().lower() if token.lower() in {"and", "or"} else token.strip()
        for token in _GPR_TOKEN_PATTERN.findall(normalised_gpr_rule)
        if token.strip()
    ]
    if not tokens:
        raise ValueError("No tokens parsed from GPR rule.")
    return tuple(tokens)


def _parse_or_expression(cursor: _TokenCursor) -> tuple[_GPRNode, _TokenCursor]:
    """Generated: validation needed.

    Description:
        Parse `or` precedence level from token stream.

    Args:
        cursor (_TokenCursor): Parsing cursor.

    Returns:
        tuple[_GPRNode, _TokenCursor]: Parsed node and updated cursor.
    """

    left_node, cursor = _parse_and_expression(cursor)
    while cursor.peek() == "or":
        _, cursor = cursor.advance()
        right_node, cursor = _parse_and_expression(cursor)
        left_node = ("OR", left_node, right_node)
    return left_node, cursor


def _parse_and_expression(cursor: _TokenCursor) -> tuple[_GPRNode, _TokenCursor]:
    """Generated: validation needed.

    Description:
        Parse `and` precedence level from token stream.

    Args:
        cursor (_TokenCursor): Parsing cursor.

    Returns:
        tuple[_GPRNode, _TokenCursor]: Parsed node and updated cursor.
    """

    left_node, cursor = _parse_primary_expression(cursor)
    while cursor.peek() == "and":
        _, cursor = cursor.advance()
        right_node, cursor = _parse_primary_expression(cursor)
        left_node = ("AND", left_node, right_node)
    return left_node, cursor


def _parse_primary_expression(cursor: _TokenCursor) -> tuple[_GPRNode, _TokenCursor]:
    """Generated: validation needed.

    Description:
        Parse one primary expression token (gene or parenthesized subtree).

    Args:
        cursor (_TokenCursor): Parsing cursor.

    Returns:
        tuple[_GPRNode, _TokenCursor]: Parsed node and updated cursor.

    Raises:
        ValueError: When expression has mismatched parentheses or invalid operator placement.
    """

    token = cursor.peek()
    if token is None:
        raise ValueError("Unexpected end of GPR expression.")
    if token == "(":
        _, cursor = cursor.advance()
        nested_node, cursor = _parse_or_expression(cursor)
        closing_token, cursor = cursor.advance()
        if closing_token != ")":
            raise ValueError("Unmatched parenthesis in GPR rule.")
        return nested_node, cursor
    if token in {"and", "or", ")"}:
        raise ValueError(f"Invalid token placement in GPR rule: '{token}'.")
    gene_token, cursor = cursor.advance()
    return gene_token, cursor


def _expand_tree_to_gene_IFPs(gpr_tree: _GPRNode) -> tuple[tuple[str, ...], ...]:
    """Generated: validation needed.

    Description:
        Expand parsed GPR tree into `AND` gene IFPs.

    Args:
        gpr_tree (_GPRNode): Parsed GPR node.

    Returns:
        tuple[tuple[str, ...], ...]: Expanded IFPs.
    """

    if isinstance(gpr_tree, str):
        return ((gpr_tree,),)
    operator, left_node, right_node = gpr_tree
    left_IFPs = _expand_tree_to_gene_IFPs(left_node)
    right_IFPs = _expand_tree_to_gene_IFPs(right_node)
    if operator == "OR":
        return left_IFPs + right_IFPs
    expanded_IFPs: list[tuple[str, ...]] = []
    for left_IFP in left_IFPs:
        for right_IFP in right_IFPs:
            expanded_IFPs.append(left_IFP + right_IFP)
    return tuple(expanded_IFPs)


def _deduplicate_IFPs(gene_IFPs: Sequence[tuple[str, ...]]) -> tuple[tuple[str, ...], ...]:
    """Generated: validation needed.

    Description:
        Deduplicate repeated genes inside IFPs and repeated IFPs overall.

    Args:
        gene_IFPs (Sequence[tuple[str, ...]]): Candidate IFPs.

    Returns:
        tuple[tuple[str, ...], ...]: Deduplicated IFPs.
    """

    seen_IFPs: set[tuple[str, ...]] = set()
    deduplicated_IFPs: list[tuple[str, ...]] = []
    for gene_IFP in gene_IFPs:
        unique_gene_order: list[str] = []
        seen_genes: set[str] = set()
        for gene_symbol in gene_IFP:
            if gene_symbol not in seen_genes:
                unique_gene_order.append(gene_symbol)
                seen_genes.add(gene_symbol)
        canonical_IFP = tuple(unique_gene_order)
        if canonical_IFP not in seen_IFPs:
            deduplicated_IFPs.append(canonical_IFP)
            seen_IFPs.add(canonical_IFP)
    return tuple(deduplicated_IFPs)
