"""
Thread-safe, disk-backed key-value cache for external API lookups.

Designed to be shared by:
- Gene sequence lookups (Ensembl, RefSeq)
  → namespaces ``ensembl_sequences`` / ``refseq_sequences``
- SMILES lookups         (future)            → namespace ``smiles_metabolite``
- Any other external API calls that are expensive and should survive process restarts

Cache files live in ``{project_root}/.lookup_cache/`` by default, or in a directory
set by the ``VmaxBuilder_CACHE_DIR`` environment variable.  Each namespace is a separate
JSON file, e.g. ``.lookup_cache/ensembl_sequences.json``.

Thread-safety
-------------
All public methods acquire an internal ``threading.Lock`` so the cache can safely
be used from ``ThreadPoolExecutor`` workers that call :meth:`set` concurrently.

Atomic writes
-------------
Saves go via ``{file}.tmp`` → :meth:`Path.replace` so a crash mid-write never
leaves a corrupt cache file.

Usage example
-------------
::

    from src.VmaxBuilder.utils.lookup_cache import LookupCache, get_default_cache_dir

    cache = LookupCache(get_default_cache_dir(), "ensembl_sequences")
    key   = sequence_cache_key("homo_sapiens", "ENSG00000139618", "canonical_only")

    if key not in cache:
        result = expensive_api_call(...)
        cache.set(key, gene_result_to_dict(result))   # saved to disk immediately

    data = cache.get(key)  # returns the stored dict

"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_DEFAULT_CACHE_SUBDIR = ".lookup_cache"


def get_default_cache_dir() -> Path:
    """Resolve the default cache directory.

    Resolution order:

    1. ``SWAMP_CACHE_DIR`` environment variable (absolute or relative path).
    1. ``VmaxBuilder_CACHE_DIR`` environment variable (legacy compatibility).
    2. ``{project_root}/.lookup_cache/``
    """
    env_override = os.environ.get("SWAMP_CACHE_DIR") or os.environ.get(
        "VmaxBuilder_CACHE_DIR"
    )
    if env_override:
        return Path(env_override).resolve()

    # Lazy import to avoid circular dependency at module load time.
    from .file_handling import get_project_root  # noqa: PLC0415

    return get_project_root() / _DEFAULT_CACHE_SUBDIR


# ---------------------------------------------------------------------------
# Core cache class
# ---------------------------------------------------------------------------


class LookupCache:
    """Thread-safe, disk-backed key-value store for a single namespace.

    Parameters
    ----------
    cache_dir:
        Directory where the JSON file for this namespace lives.
    namespace:
        Logical name of the cache (becomes the JSON filename, e.g.
        ``"ensembl_sequences"`` → ``cache_dir/ensembl_sequences.json``).
    autosave:
        When ``True`` (the default) every :meth:`set` / :meth:`set_many` call
        flushes the updated data to disk immediately.  Set to ``False`` for
        bulk-loading scenarios where you want to call :meth:`save` once at the
        end.
    """

    def __init__(
        self,
        cache_dir: Path,
        namespace: str,
        autosave: bool = True,
    ) -> None:
        self._path = (cache_dir / namespace).with_suffix(".json")
        self._lock = threading.Lock()
        self._autosave = autosave
        self._data: dict[str, Any] = self._load_from_disk()

    # ------------------------------------------------------------------
    # Internal I/O
    # ------------------------------------------------------------------

    def _load_from_disk(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
        return {}

    def _write_to_disk(self) -> None:
        """Atomic write via a temp file so crashes never corrupt the cache."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        try:
            with tmp.open("w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2)
            tmp.replace(self._path)
        except OSError:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            raise

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str) -> Any | None:
        """Return the cached value for *key*, or ``None`` if absent."""
        with self._lock:
            return self._data.get(key)

    def set(self, key: str, value: Any) -> None:
        """Store *value* under *key* and write to disk if *autosave* is on."""
        with self._lock:
            self._data[key] = value
            if self._autosave:
                self._write_to_disk()

    def set_many(self, items: dict[str, Any]) -> None:
        """Store multiple key-value pairs in one operation (single disk write)."""
        with self._lock:
            self._data.update(items)
            if self._autosave:
                self._write_to_disk()

    def save(self) -> None:
        """Flush current state to disk (useful when *autosave* is ``False``)."""
        with self._lock:
            self._write_to_disk()

    def invalidate(self, key: str) -> None:
        """Remove a single cached entry and persist."""
        with self._lock:
            self._data.pop(key, None)
            if self._autosave:
                self._write_to_disk()

    def clear(self) -> None:
        """Remove all entries and persist an empty cache file."""
        with self._lock:
            self._data.clear()
            self._write_to_disk()

    def __contains__(self, key: str) -> bool:
        with self._lock:
            return key in self._data

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)

    def keys(self) -> list[str]:
        """Return a snapshot of all cache keys."""
        with self._lock:
            return list(self._data.keys())

    def hits_and_misses(self, keys: list[str]) -> tuple[list[str], list[str]]:
        """Split *keys* into *(cached_keys, missing_keys)*.

        Use this before making API calls to determine which items can be
        served from cache and which need fetching::

            hits, misses = cache.hits_and_misses(gene_symbols)
            # only fetch 'misses', reuse 'hits' directly
        """
        with self._lock:
            hits = [k for k in keys if k in self._data]
            misses = [k for k in keys if k not in self._data]
        return hits, misses

    @property
    def path(self) -> Path:
        """Absolute path to the JSON file backing this cache."""
        return self._path

    def __repr__(self) -> str:
        return (
            f"LookupCache(namespace={self._path.stem!r}, "
            f"entries={len(self._data)}, path={self._path})"
        )


@dataclass(frozen=True)
class SequenceRecord:
    """JSON-friendly record describing one retrieved sequence."""

    sequence: str
    source: str
    accession: str
    is_canonical: bool | None = None


@dataclass(frozen=True)
class GeneSequenceResult:
    """Container for sequence lookup results for one gene symbol."""

    gene_symbol: str
    sequences: list[SequenceRecord]
    errors: list[Any] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Sequence-specific helpers
# ---------------------------------------------------------------------------


def sequence_cache_key(species: str, gene_symbol: str, mode: str) -> str:
    """Canonical cache key for a :class:`GeneSequenceResult`.

    Parameters
    ----------
    species:
        The provider-level species string (e.g. ``"homo_sapiens"``).
    gene_symbol:
        Gene identifier / symbol.
    mode:
        The :class:`~src.VmaxBuilder.sequence_retrieval.types.SequenceMode` value
        string (e.g. ``"canonical_only"`` or ``"all_isoforms"``).
    """
    return f"{species}:{gene_symbol}:{mode}"


def gene_result_to_dict(result: GeneSequenceResult) -> dict[str, Any]:
    """Generated: validation needed.

    Description:
        Serialize sequence result object to JSON-safe dictionary.

    Args:
        result (GeneSequenceResult): Sequence result to serialize.

    Returns:
        dict[str, Any]: JSON-safe representation of result.
    """
    return {
        "gene_symbol": result.gene_symbol,
        "sequences": [
            {
                "sequence": r.sequence,
                "source": r.source,
                "accession": r.accession,
                "is_canonical": r.is_canonical,
            }
            for r in result.sequences
        ],
        "errors": result.errors,
    }


def dict_to_gene_result(data: dict[str, Any]) -> GeneSequenceResult:
    """Generated: validation needed.

    Description:
        Deserialize cached dictionary back to sequence result object.

    Args:
        data (dict[str, Any]): Cached representation to deserialize.

    Returns:
        GeneSequenceResult: Reconstructed sequence result.
    """

    return GeneSequenceResult(
        gene_symbol=data["gene_symbol"],
        sequences=[
            SequenceRecord(
                sequence=r["sequence"],
                source=r["source"],
                accession=r["accession"],
                is_canonical=r.get("is_canonical"),
            )
            for r in data.get("sequences", [])
        ],
        errors=data.get("errors", []),
    )


# ---------------------------------------------------------------------------
# SMILES-specific helpers (ready for use once SMILES retrieval is implemented)
# ---------------------------------------------------------------------------


def smiles_cache_key(database: str, metabolite_id: str) -> str:
    """Canonical cache key for a metabolite SMILES lookup.

    Parameters
    ----------
    database:
        Source database name (e.g. ``"chebi"``, ``"hmdb"``).
    metabolite_id:
        The metabolite identifier in that database.
    """
    return f"{database}:{metabolite_id}"
