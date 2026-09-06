from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from VmaxBuilder.stages.Kcat.Kcat_utils import (
    GeneMainSubstratePrediction,
    ReactionMainSubstratePrediction,
)
from VmaxBuilder.stages.Vmax.default.reaction_resolving import (
    DefaultVmaxReactionResolving,
)


class _FakeGene:
    def __init__(self, gene_id: str):
        self.id = gene_id


class _FakeReaction:
    def __init__(self, reaction_id: str, gene_rule: str, genes: list[_FakeGene]):
        self.id = reaction_id
        self.gene_reaction_rule = gene_rule
        self.genes = genes


class _FakeModel:
    def __init__(self, reactions: list[_FakeReaction]):
        self.reactions = reactions


def _make_prediction() -> ReactionMainSubstratePrediction:
    gene_prediction = GeneMainSubstratePrediction(
        gene_id="g1",
        reaction_id="R1",
        main_substrate="m1_c",
        main_substrate_compartment="c",
        main_substrate_prediction_value=2.0,
        metabolites_considered={"m1_c": 1.0},
        substrate_stoichiometries={"m1_c": -1.0},
        stoichiometry_adjusted_main_substrate_prediction_value=3.0,
        metabolites_stoichiometry_adjusted_considered={"m1_c": 1.0},
    )
    return ReactionMainSubstratePrediction(
        reaction_id="R1",
        gene_main_substrate_predictions={"g1": gene_prediction},
        genes_considered={"g1"},
        substrate_stoichiometries={"m1_c": -1.0},
    )


def _make_resolver(
    save_ifp_artifact: bool,
    include_gene_details: bool = False,
) -> DefaultVmaxReactionResolving:
    resolver = object.__new__(DefaultVmaxReactionResolving)
    resolver.logger = SimpleNamespace(
        attention=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None
    )
    resolver.full_config = SimpleNamespace(
        protein=SimpleNamespace(trim_enable=False),
        Vmax=SimpleNamespace(
            trim_genes_remain_part_for_Kcat=False,
            save_ifp_sample_abundance_artifact=save_ifp_artifact,
            include_gene_details_in_ifp_sample_abundance_artifact=include_gene_details,
        ),
    )
    return resolver


@pytest.mark.unit
def test_reaction_resolving_keeps_compact_ifp_artifact_by_default() -> None:
    resolver = _make_resolver(save_ifp_artifact=True)
    ifp_df = pd.DataFrame({"sample_1": [2.0]}, index=["IFP1"])
    predictions = {"R1": _make_prediction()}
    trimming_output: dict = {}
    reaction_to_ifp_mapping = {"R1": {"IFPs": ["IFP1"]}}
    gene_to_ifp_mapping = {"g1": {"IFPs": ["IFP1"]}}
    model = _FakeModel([_FakeReaction("R1", "g1", [_FakeGene("g1")])])

    reaction_capacity_df, ifp_artifact = resolver.resolve_reaction_capacity(
        ifp_df,
        predictions,
        trimming_output,
        reaction_to_ifp_mapping,
        gene_to_ifp_mapping,
        model,  # ty: ignore[arg-type]
    )

    assert reaction_capacity_df.loc["R1", "sample_1"] == pytest.approx(6.0)
    assert "sample_1" in ifp_artifact
    assert "genes" not in ifp_artifact["sample_1"]["R1"]
    ifp_entry = ifp_artifact["sample_1"]["R1"]["IFPs"]["IFP1"]
    assert ifp_entry["abundance"] == pytest.approx(2.0)
    assert "expression" not in str(ifp_entry)
    assert "genes" not in ifp_entry


@pytest.mark.unit
def test_reaction_resolving_includes_gene_details_only_when_requested() -> None:
    resolver = _make_resolver(save_ifp_artifact=True, include_gene_details=True)
    ifp_df = pd.DataFrame({"sample_1": [2.0]}, index=["IFP1"])
    predictions = {"R1": _make_prediction()}
    trimming_output: dict = {}
    reaction_to_ifp_mapping = {"R1": {"IFPs": ["IFP1"]}}
    gene_to_ifp_mapping = {"g1": {"IFPs": ["IFP1"]}}
    model = _FakeModel([_FakeReaction("R1", "g1", [_FakeGene("g1")])])

    _, ifp_artifact = resolver.resolve_reaction_capacity(
        ifp_df,
        predictions,
        trimming_output,
        reaction_to_ifp_mapping,
        gene_to_ifp_mapping,
        model,  # ty: ignore[arg-type]
    )

    assert "genes" in ifp_artifact["sample_1"]["R1"]
    ifp_entry = ifp_artifact["sample_1"]["R1"]["IFPs"]["IFP1"]
    assert "genes" in ifp_entry
    assert ifp_entry["genes"]["g1"]["main_substrate_prediction_value"] == pytest.approx(2.0)
