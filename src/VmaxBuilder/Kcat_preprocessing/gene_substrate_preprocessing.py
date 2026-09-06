from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np
from cobra.core.model import Model

from VmaxBuilder.base.classes import (
    BaseImplementation,
    DiagnosticOutputSpec,
    RealImplementation,
)
from VmaxBuilder.base.configs import FullConfig, InputSpec, OutputSpec, Scaffold
from VmaxBuilder.utils.extra_utils import remove_compartment


def get_gene_substrate_mapping(
    cobra_model: Model,
) -> dict[str, set[str]]:
    gene_substrate_mapping = {}

    reactions = cobra_model.reactions
    for reaction in reactions:
        if not reaction.gene_reaction_rule:
            continue
        if not reaction.gene_reaction_rule.strip():
            continue
        if reaction.gene_reaction_rule.strip().lower() == "none":
            continue
        if len(reaction.genes) < 1:  # . genes is not a true list regular if .genes is dubious
            continue
        # get substrates
        substrates = [
            remove_compartment(met.id)
            for met in reaction.metabolites
            if reaction.metabolites[met] < 0
        ]
        if not substrates:
            continue

        for gene in reaction.genes:
            if gene.id not in gene_substrate_mapping:
                gene_substrate_mapping[gene.id] = set()
            for substrate in substrates:
                gene_substrate_mapping[gene.id].add(substrate)
    # sort and sort set
    gene_substrate_mapping = {
        gene: set(sorted(substrates)) for gene, substrates in gene_substrate_mapping.items()
    }
    gene_substrate_mapping = dict(sorted(gene_substrate_mapping.items()))

    return gene_substrate_mapping


def get_gene_substrate_mapping_diff(
    gene_substrate_mapping_1: dict[str, set[str]],
    gene_substrate_mapping_2: dict[str, set[str]],
):
    diff_mapping = {}
    for gene, substrates_1 in gene_substrate_mapping_1.items():
        substrates_2 = gene_substrate_mapping_2.get(gene, set())
        diff_substrates = substrates_1 - substrates_2
        if diff_substrates:
            diff_mapping[gene] = diff_substrates
    return diff_mapping
