from dataclasses import dataclass

from VmaxBuilder.base.enums import ReactionNotation


@dataclass(slots=True)
class ModelConfig:
    """Generated: validation needed.

    Description:
        Configuration for model loading and reaction notation convention.

    Args:
        reaction_notation (ReactionNotation): Reaction identifier convention.
        make_copy (bool): Copy model at preprocessing start before mutation. Default True.
        id_type (str): Canonical identifier provider expected in model entities.
        level (str): Gene or transcript level granularity.
    """

    reaction_notation: ReactionNotation = ReactionNotation.STANDARD
    make_copy: bool = True
    gene_id_type: str = "ensembl"
    level: str = "gene"
