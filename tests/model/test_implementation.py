from __future__ import annotations

from pathlib import Path

import pandas as pd
from cobra import Metabolite, Model, Reaction

from VmaxBuilder.config import APIConfig, LoadingPolicy
from VmaxBuilder.core.protocols import Scaffold
from VmaxBuilder.model import DefaultModelStageImplementation


class _FakeTranslationService:
    def __init__(self, transcript_df: pd.DataFrame) -> None:
        self.transcript_df = transcript_df
        self.calls = 0

    def build_gene_transcript_dataframe(
        self,
        gene_ids: list[str],
        *,
        gene_id_type: str,
        species: str | None,
        provider: str,
        max_workers: int,
        batch_size: int,
    ) -> pd.DataFrame:
        _ = gene_ids, gene_id_type, species, provider, max_workers, batch_size
        self.calls += 1
        return self.transcript_df.copy()


def _make_model() -> Model:
    model = Model("model")
    a_met = Metabolite("a_c")
    b_met = Metabolite("b_c")

    reaction = Reaction("R1")
    reaction.add_metabolites({a_met: -1.0, b_met: 1.0})
    reaction.gene_reaction_rule = "ENSG001"
    reaction.bounds = (-10.0, 10.0)

    model.add_reactions([reaction])
    return model


def _make_scaffold() -> Scaffold:
    return {
        "inputs": {},
        "artifacts": {},
        "outputs": {},
        "metadata": {},
        "diagnostics": {},
        "extras": {},
    }


def test_model_stage_builds_transcript_mapping_artifacts_for_transcript_target(
    tmp_path: Path,
) -> None:
    transcript_df = pd.DataFrame(
        [
            {
                "transcript_id": "ENST001",
                "gene_id": "ENSG001",
                "is_protein_coding": True,
                "is_canonical": True,
                "peptide_len": 10,
                "cdna_len": 30,
                "peptide_seq": "MPEPTIDEAA",
                "cdna_seq": "ATG" * 10,
            },
            {
                "transcript_id": "ENST002",
                "gene_id": "ENSG001",
                "is_protein_coding": False,
                "is_canonical": False,
                "peptide_len": None,
                "cdna_len": 21,
                "peptide_seq": None,
                "cdna_seq": "ATG" * 7,
            },
        ]
    )

    implementation = DefaultModelStageImplementation(
        translation_service=_FakeTranslationService(transcript_df),
    )
    config = APIConfig(
        loading=LoadingPolicy(
            model_object=_make_model(),
            output_path=tmp_path,
        )
    )
    config.run_target_transcript_gene_level = "transcript"

    scaffold = implementation.run(_make_scaffold(), config)

    assert "gene_transcript_mapping" in scaffold["artifacts"]
    assert scaffold["artifacts"]["transcript_to_gene_mapping"] == {
        "ENST001": "ENSG001",
        "ENST002": "ENSG001",
    }
    assert scaffold["artifacts"]["gene_to_transcript_mapping"] == {
        "ENSG001": ["ENST001", "ENST002"]
    }
    assert scaffold["artifacts"]["protein_coding_transcripts"] == ["ENST001"]
    assert scaffold["artifacts"]["canonical_transcripts"] == ["ENST001"]
    assert list(scaffold["artifacts"]["transcript_sequences"].columns) == [
        "transcript_id",
        "gene_id",
        "peptide_len",
        "cdna_len",
        "peptide_seq",
        "cdna_seq",
    ]
