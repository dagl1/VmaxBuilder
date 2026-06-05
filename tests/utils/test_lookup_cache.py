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
    smiles_cache_key,
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


@pytest.mark.unit
def test_lookup_cache_clear_removes_all_entries(tmp_path: Path) -> None:
    cache = LookupCache(tmp_path, "ns")
    cache.set_many({"x": 1, "y": 2})
    assert len(cache) == 2

    cache.clear()

    assert len(cache) == 0
    assert "x" not in cache


@pytest.mark.unit
def test_lookup_cache_keys_returns_snapshot(tmp_path: Path) -> None:
    cache = LookupCache(tmp_path, "ns")
    cache.set_many({"a": 1, "b": 2})

    keys = cache.keys()

    assert sorted(keys) == ["a", "b"]


@pytest.mark.unit
def test_lookup_cache_repr_contains_namespace(tmp_path: Path) -> None:
    cache = LookupCache(tmp_path, "my_ns")
    assert "my_ns" in repr(cache)


@pytest.mark.unit
def test_lookup_cache_autosave_false_does_not_write_immediately(tmp_path: Path) -> None:
    cache = LookupCache(tmp_path, "lazy", autosave=False)
    cache.set("key", "value")

    # File not yet written
    cache_file = tmp_path / "lazy.json"
    assert not cache_file.exists()

    cache.save()
    assert cache_file.exists()


@pytest.mark.unit
def test_lookup_cache_handles_corrupt_json_gracefully(tmp_path: Path) -> None:
    cache_file = tmp_path / "corrupt.json"
    cache_file.write_text("{{not valid json", encoding="utf-8")

    cache = LookupCache(tmp_path, "corrupt")
    assert len(cache) == 0


@pytest.mark.unit
def test_smiles_cache_key_format() -> None:
    key = smiles_cache_key("chebi", "CHEBI:15422")
    assert key == "chebi:CHEBI:15422"


@pytest.mark.unit
def test_lookup_cache_get_missing_key_returns_none(tmp_path: Path) -> None:
    cache = LookupCache(tmp_path, "empty")
    assert cache.get("nonexistent") is None
