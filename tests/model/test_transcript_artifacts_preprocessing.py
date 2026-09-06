from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pytest
from cobra import Metabolite, Model, Reaction

from VmaxBuilder.base.classes import ImplementationConfig
from VmaxBuilder.base.configs import FullConfig, RunConfig, TranscriptProcessingConfig


@dataclass(slots=True)
class _ModelConfigStub:
    id_type: str = "ensembl"
    level: str = "gene"


class _FakeTranslationService:
    def __init__(self, transcript_df: pd.DataFrame) -> None:
        self.transcript_df = transcript_df

    def build_gene_transcript_dataframe(
        self,
        gene_ids: list[str],
        *,
        gene_id_type: str,
        species: str | None,
        provider: str,
        max_workers: int,
        batch_size: int,
        include_sequence_metadata: bool = True,
        include_cdna_sequence: bool = False,
    ) -> pd.DataFrame:
        _ = (
            gene_ids,
            gene_id_type,
            species,
            provider,
            max_workers,
            batch_size,
            include_sequence_metadata,
            include_cdna_sequence,
        )
        return self.transcript_df.copy()


def _make_model() -> Model:
    model = Model("model")
    a_met = Metabolite("a_c")
    b_met = Metabolite("b_c")

    reaction = Reaction("R1")
    reaction.add_metabolites({a_met: -1.0, b_met: 1.0})
    reaction.gene_reaction_rule = "ENSG001"
    reaction.bounds = (0.0, 10.0)
    model.add_reactions([reaction])
    return model


@pytest.fixture
def full_config(tmp_path: Path) -> FullConfig:
    run_config = RunConfig(output_dir=tmp_path, run_name="model_transcripts")
    return FullConfig(
        model=_ModelConfigStub(),
        protein=ImplementationConfig(),
        allocation=ImplementationConfig(),
        Kcat=ImplementationConfig(),
        Vmax=ImplementationConfig(),
        run=run_config,
        paths=run_config.paths,
        transcripts=TranscriptProcessingConfig(),
    )


def _make_transcript_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "transcript_id": "ENST001",
                "gene_id": "ENSG001",
                "is_protein_coding": True,
                "is_canonical": True,
                "translation_id": "ENSP001",
                "peptide_len": 8,
                "cdna_len": 24,
                "peptide_seq": "MPEPTIDE",
                "cdna_seq": "ATG" * 8,
            },
            {
                "transcript_id": "ENST002",
                "gene_id": "ENSG001",
                "is_protein_coding": True,
                "is_canonical": False,
                "translation_id": "ENSP002",
                "peptide_len": 4,
                "cdna_len": 12,
                "peptide_seq": "MALT",
                "cdna_seq": "ATG" * 4,
            },
        ]
    )


def _load_build_transcript_artifacts_function():
    module_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "VmaxBuilder"
        / "stages"
        / "model"
        / "default"
        / "preprocessing.py"
    )
    module_spec = importlib.util.spec_from_file_location(
        "model_default_preprocessing",
        module_path,
    )
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError("Could not load model preprocessing module for test.")

    loaded_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(loaded_module)
    return loaded_module._build_transcript_artifacts_for_model


@pytest.mark.integration
def test_build_transcript_artifacts_default_keeps_canonical_only(
    full_config: FullConfig,
) -> None:
    build_transcript_artifacts = _load_build_transcript_artifacts_function()
    service = _FakeTranslationService(_make_transcript_df())

    artifacts = build_transcript_artifacts(
        model=_make_model(),
        config=full_config,
        translation_service=service,
    )

    transcript_df = artifacts["gene_transcript_mapping"]
    assert transcript_df["transcript_id"].tolist() == ["ENST001"]
    assert artifacts["canonical_transcripts"] == ["ENST001"]
    assert artifacts["gene_to_transcript_mapping"] == {"ENSG001": ["ENST001"]}
    assert "transcript_sequences" not in artifacts


@pytest.mark.integration
def test_build_transcript_artifacts_can_keep_alternative_transcripts(
    full_config: FullConfig,
) -> None:
    build_transcript_artifacts = _load_build_transcript_artifacts_function()
    full_config.transcripts.retrieve_alternative_transcripts = True
    service = _FakeTranslationService(_make_transcript_df())

    artifacts = build_transcript_artifacts(
        model=_make_model(),
        config=full_config,
        translation_service=service,
    )

    transcript_df = artifacts["gene_transcript_mapping"]
    assert transcript_df["transcript_id"].tolist() == ["ENST001", "ENST002"]
    assert artifacts["canonical_transcripts"] == ["ENST001"]
    assert artifacts["gene_to_transcript_mapping"] == {
        "ENSG001": ["ENST001", "ENST002"]
    }

