from __future__ import annotations

from cobra import Metabolite, Model, Reaction

from VmaxBuilder.config import APIConfig
from VmaxBuilder.core.protocols import Scaffold
from VmaxBuilder.Kcat import (
    DefaultKcatGPRImplementation,
    DefaultKcatPreprocessingImplementation,
    DefaultKcatStageCoordinator,
    DefaultSmilesGettersImplementation,
    DefaultUniKPImplementation,
    KcatStageOrchestrator,
)
from VmaxBuilder.Kcat.gpr_preprocessing import get_unique_gpr_rules


def _make_scaffold() -> Scaffold:
    return {
        "inputs": {},
        "artifacts": {},
        "outputs": {},
        "metadata": {},
        "diagnostics": {},
        "extras": {},
    }


def test_kcat_scaffold_exports_are_available() -> None:
    assert isinstance(DefaultUniKPImplementation(), DefaultUniKPImplementation)
    assert isinstance(
        DefaultKcatPreprocessingImplementation(),
        DefaultKcatPreprocessingImplementation,
    )
    assert isinstance(DefaultKcatGPRImplementation(), DefaultKcatGPRImplementation)
    assert isinstance(
        DefaultSmilesGettersImplementation(),
        DefaultSmilesGettersImplementation,
    )
    assert isinstance(DefaultKcatStageCoordinator(), DefaultKcatStageCoordinator)
    assert isinstance(KcatStageOrchestrator(), KcatStageOrchestrator)


def test_kcat_stage_orchestrator_scaffold_run_populates_placeholder_keys() -> None:
    orchestrator = KcatStageOrchestrator()
    config = APIConfig()
    scaffold = _make_scaffold()

    result = orchestrator.run(scaffold, config)

    assert "kcat_ifp_mapping" in result["artifacts"]
    assert "kcat_smiles_mapping" in result["artifacts"]
    assert "kcat_preprocessed_inputs" in result["artifacts"]
    assert "kcat_predictions" in result["artifacts"]
    assert result["metadata"]["kcat_stage"]["status"] == "placeholder_not_implemented"


def test_kcat_gpr_implementation_extracts_unique_rules_from_scaffold_model() -> None:
    model = Model("gpr-test")
    metabolite = Metabolite("metabolite_c")

    first_reaction = Reaction("reaction_1")
    first_reaction.add_metabolites({metabolite: -1.0})
    first_reaction.gene_reaction_rule = "gene_a and gene_b"

    duplicate_reaction = Reaction("reaction_2")
    duplicate_reaction.add_metabolites({metabolite: -1.0})
    duplicate_reaction.gene_reaction_rule = "gene_a and gene_b"

    distinct_reaction = Reaction("reaction_3")
    distinct_reaction.add_metabolites({metabolite: -1.0})
    distinct_reaction.gene_reaction_rule = "gene_c"

    model.add_reactions([first_reaction, duplicate_reaction, distinct_reaction])

    scaffold = _make_scaffold()
    scaffold["artifacts"]["model"] = model

    result = get_unique_gpr_rules(scaffold)

    assert result == {"gene_a and gene_b", "gene_c"}
