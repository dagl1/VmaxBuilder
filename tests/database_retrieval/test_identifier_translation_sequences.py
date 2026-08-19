from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pytest

from VmaxBuilder.database_retrieval.identifier_translation import (
    IdentifierTranslationService,
)


@dataclass(slots=True)
class _FakeResponse:
    status_code: int
    payload: dict[str, str]

    @property
    def ok(self) -> bool:
        return self.status_code == 200

    def json(self) -> dict[str, str]:
        return self.payload


@pytest.mark.integration
def test_enrich_transcript_dataframe_with_sequences_fetches_all_transcript_aa(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    transcript_df = pd.DataFrame(
        {
            "transcript_id": ["ENST_CANONICAL", "ENST_ALT"],
            "gene_id": ["ENSG001", "ENSG001"],
        }
    )

    def fake_get(url: str, headers: dict[str, str], timeout: int) -> _FakeResponse:
        _ = headers, timeout
        if "/lookup/id/ENST_CANONICAL" in url:
            return _FakeResponse(200, {"Translation": {"id": "ENSP_CANONICAL"}})
        if "/lookup/id/ENST_ALT" in url:
            return _FakeResponse(200, {"Translation": {"id": "ENSP_ALT"}})
        if "/sequence/id/ENSP_CANONICAL" in url:
            return _FakeResponse(200, {"seq": "MPEPTIDE"})
        if "/sequence/id/ENSP_ALT" in url:
            return _FakeResponse(200, {"seq": "MALT"})
        return _FakeResponse(404, {})

    monkeypatch.setattr(
        "VmaxBuilder.database_retrieval.identifier_translation.requests.get",
        fake_get,
    )
    monkeypatch.setattr(
        "VmaxBuilder.database_retrieval.identifier_translation.get_default_cache_dir",
        lambda: tmp_path,
    )

    service = IdentifierTranslationService()
    enriched_df = service.enrich_transcript_dataframe_with_sequences(transcript_df)

    assert enriched_df["transcript_id"].tolist() == ["ENST_CANONICAL", "ENST_ALT"]
    assert enriched_df["translation_id"].tolist() == ["ENSP_CANONICAL", "ENSP_ALT"]
    assert enriched_df["peptide_seq"].tolist() == ["MPEPTIDE", "MALT"]
    assert enriched_df["peptide_len"].tolist() == [8, 4]


@pytest.mark.integration
def test_build_gene_transcript_dataframe_enriches_sequences_from_ensembl(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    mygene_hits = [
        {
            "query": "ENSG001",
            "ensembl": [
                {
                    "gene": "ENSG001",
                    "transcript": "ENST_CANONICAL",
                    "translation": {"id": "ENSP_CANONICAL"},
                },
                {
                    "gene": "ENSG001",
                    "transcript": "ENST_ALT",
                    "translation": {"id": "ENSP_ALT"},
                },
            ],
            "ensembl.canonical_transcript": "ENST_CANONICAL",
            "type_of_gene": "protein-coding",
        }
    ]

    def fake_query_chunk(
        chunk: list[str],
        source_scope: str,
        field_string: str,
        species: str | None,
    ) -> list[dict[str, object]]:
        _ = chunk, source_scope, field_string, species
        return mygene_hits

    def fake_get(url: str, headers: dict[str, str], timeout: int) -> _FakeResponse:
        _ = headers, timeout
        if "/lookup/id/ENST_CANONICAL" in url:
            return _FakeResponse(200, {"Translation": {"id": "ENSP_CANONICAL"}})
        if "/lookup/id/ENST_ALT" in url:
            return _FakeResponse(200, {"Translation": {"id": "ENSP_ALT"}})
        if "/sequence/id/ENSP_CANONICAL" in url:
            return _FakeResponse(200, {"seq": "MPEPTIDE"})
        if "/sequence/id/ENSP_ALT" in url:
            return _FakeResponse(200, {"seq": "MALT"})
        return _FakeResponse(404, {})

    monkeypatch.setattr(
        IdentifierTranslationService,
        "_query_mygene_chunk",
        staticmethod(fake_query_chunk),
    )
    monkeypatch.setattr(
        "VmaxBuilder.database_retrieval.identifier_translation.requests.get",
        fake_get,
    )
    monkeypatch.setattr(
        "VmaxBuilder.database_retrieval.identifier_translation.get_default_cache_dir",
        lambda: tmp_path,
    )

    service = IdentifierTranslationService()
    transcript_df = service.build_gene_transcript_dataframe(
        ["ENSG001"],
        gene_id_type="ensembl_gene_id",
        include_sequence_metadata=True,
    )

    assert transcript_df["transcript_id"].tolist() == ["ENST_CANONICAL", "ENST_ALT"]
    assert transcript_df["is_canonical"].tolist() == [True, False]
    assert transcript_df["peptide_seq"].tolist() == ["MPEPTIDE", "MALT"]
    assert transcript_df["peptide_len"].tolist() == [8, 4]

