from __future__ import annotations

from pathlib import Path

import pytest

from VmaxBuilder.utils.lookup_cache import (
    GeneSequenceResult,
    LookupCache,
    SequenceRecord,
    dict_to_gene_result,
    gene_result_to_dict,
    get_default_cache_dir,
    sequence_cache_key,
)


@pytest.mark.unit
def test_get_default_cache_dir_honors_environment_variable(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VmaxBuilder_CACHE_DIR", str(tmp_path / "cache"))

    assert get_default_cache_dir() == (tmp_path / "cache").resolve()


@pytest.mark.integration
def test_lookup_cache_round_trip(tmp_path: Path) -> None:
    cache = LookupCache(tmp_path, "genes")
    cache.set("alpha", {"value": 1})

    assert cache.get("alpha") == {"value": 1}
    assert "alpha" in cache
    assert cache.path == tmp_path / "genes.json"

    reopened_cache = LookupCache(tmp_path, "genes")
    assert reopened_cache.get("alpha") == {"value": 1}


@pytest.mark.integration
def test_lookup_cache_hits_and_misses_and_invalidation(tmp_path: Path) -> None:
    cache = LookupCache(tmp_path, "genes")
    cache.set_many({"a": 1, "b": 2})

    hits, misses = cache.hits_and_misses(["b", "c", "a"])
    assert hits == ["b", "a"]
    assert misses == ["c"]

    cache.invalidate("a")
    assert "a" not in cache


@pytest.mark.unit
def test_gene_result_round_trip_conversion() -> None:
    result = GeneSequenceResult(
        gene_symbol="BRCA1",
        sequences=[
            SequenceRecord(
                sequence="AAA",
                source="ensembl",
                accession="ENST1",
                is_canonical=True,
            )
        ],
        errors=["none"],
    )

    serialized = gene_result_to_dict(result)
    reconstructed = dict_to_gene_result(serialized)

    assert reconstructed == result
    assert (
        sequence_cache_key(
            "human",
            "BRCA1",
            "canonical_only",
        )
        == "human:BRCA1:canonical_only"
    )
