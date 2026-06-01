from __future__ import annotations

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
