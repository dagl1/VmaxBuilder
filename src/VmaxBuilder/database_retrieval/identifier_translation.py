"""Generated: validation needed.

Description:
    Identifier translation utilities for expression/model harmonisation and
    transcript-to-gene mapping.
"""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

import mygene
import pandas as pd


@dataclass(slots=True)
class IdentifierTranslationResult:
    """Generated: validation needed.

    Description:
        Translation output for one source->target identifier mapping attempt.

    Args:
        mapped_identifiers (dict[str, str]): Source identifier to resolved target identifier.
        unresolved_identifiers (list[str]):
            Source identifiers without resolved target mapping.
    """

    mapped_identifiers: dict[str, str]
    unresolved_identifiers: list[str]


class IdentifierTranslationService:
    """Generated: validation needed.

    Description:
        Translate identifier namespaces and build transcript-to-gene mapping tables
        using network APIs with threaded execution.
    """

    _TARGET_FIELDS: dict[str, tuple[str, ...]] = {
        "ensembl_gene_id": ("ensembl.gene", "ensemblgene"),
        "symbol": ("symbol",),
        "entrez_gene_id": ("entrezgene",),
    }

    _SOURCE_SCOPE_BY_ID_TYPE: dict[str, str] = {
        "symbol": "symbol,alias",
        "entrez_gene_id": "entrezgene",
        "ensembl_gene_id": "ensembl.gene,ensemblgene",
        "ensembl_transcript_id": "ensembl.transcript",
    }

    def translate_identifiers(
        self,
        identifiers: Sequence[str],
        *,
        source_id_type: str,
        target_id_type: str,
        species: str | None = None,
        provider: str = "auto",
        max_workers: int = 8,
        batch_size: int = 500,
    ) -> IdentifierTranslationResult:
        """Generated: validation needed.

        Description:
            Translate identifiers from one namespace into another with partial-result support.

        Args:
            identifiers (Sequence[str]): Source identifiers to translate.
            source_id_type (str): Source identifier namespace.
            target_id_type (str): Target identifier namespace.
            species (str | None): Optional species hint forwarded to provider.
            provider (str): Translation provider key. Supported values: auto, mygene.
            max_workers (int): Maximum number of parallel worker threads.
            batch_size (int): Number of identifiers per provider query chunk.

        Returns:
            IdentifierTranslationResult: Mapping output and unresolved identifiers list.

        Raises:
            ValueError: If provider or id-type configuration is unsupported.
        """

        deduplicated_identifiers = self._deduplicate_identifiers(identifiers)
        if source_id_type == target_id_type:
            return IdentifierTranslationResult(
                mapped_identifiers={
                    identifier: identifier for identifier in deduplicated_identifiers
                },
                unresolved_identifiers=[],
            )

        if provider not in {"auto", "mygene"}:
            raise ValueError("provider must be 'auto' or 'mygene'.")
        if provider == "auto":
            provider = "mygene"
        if provider != "mygene":
            raise ValueError("Unsupported provider.")

        resolved_mapping = self._translate_with_mygene(
            identifiers=deduplicated_identifiers,
            source_id_type=source_id_type,
            target_id_type=target_id_type,
            species=species,
            max_workers=max_workers,
            batch_size=batch_size,
        )
        unresolved_identifiers = [
            identifier
            for identifier in deduplicated_identifiers
            if identifier not in resolved_mapping
        ]
        return IdentifierTranslationResult(
            mapped_identifiers=resolved_mapping,
            unresolved_identifiers=unresolved_identifiers,
        )

    def build_transcript_gene_dataframe(
        self,
        transcript_ids: Sequence[str],
        *,
        transcript_id_type: str,
        target_gene_id_type: str,
        species: str | None = None,
        provider: str = "auto",
        max_workers: int = 8,
        batch_size: int = 500,
    ) -> pd.DataFrame:
        """Generated: validation needed.

        Description:
            Build transcript-to-gene mapping dataframe for transcript-level expression inputs.

        Args:
            transcript_ids (Sequence[str]):
                Transcript identifiers present in expression table.
            transcript_id_type (str): Transcript identifier namespace.
            target_gene_id_type (str): Target gene identifier namespace.
            species (str | None): Optional species hint forwarded to provider.
            provider (str): Translation provider key. Supported values: auto, mygene.
            max_workers (int): Maximum number of parallel worker threads.
            batch_size (int): Number of identifiers per provider query chunk.

        Returns:
            pd.DataFrame: Mapping table with transcript_id and gene_id columns.
        """

        translation_result = self.translate_identifiers(
            transcript_ids,
            source_id_type=transcript_id_type,
            target_id_type=target_gene_id_type,
            species=species,
            provider=provider,
            max_workers=max_workers,
            batch_size=batch_size,
        )
        rows = [
            {"transcript_id": transcript_id, "gene_id": gene_id}
            for transcript_id, gene_id in translation_result.mapped_identifiers.items()
        ]
        return pd.DataFrame(rows, columns=["transcript_id", "gene_id"])

    @staticmethod
    def _deduplicate_identifiers(identifiers: Sequence[str]) -> list[str]:
        """Generated: validation needed.

        Description:
            Deduplicate and strip identifiers while preserving input encounter order.

        Args:
            identifiers (Sequence[str]): Raw identifier sequence.

        Returns:
            list[str]: Deduplicated non-empty identifiers.
        """

        cleaned_identifiers = [str(identifier).strip() for identifier in identifiers]
        return list(
            dict.fromkeys(identifier for identifier in cleaned_identifiers if identifier)
        )

    def _translate_with_mygene(
        self,
        *,
        identifiers: Sequence[str],
        source_id_type: str,
        target_id_type: str,
        species: str | None,
        max_workers: int,
        batch_size: int,
    ) -> dict[str, str]:
        """Generated: validation needed.

        Description:
            Translate identifier chunks through MyGene queries and merge first-hit mappings.

        Args:
            identifiers (Sequence[str]): Identifiers to map.
            source_id_type (str): Source identifier namespace.
            target_id_type (str): Target identifier namespace.
            species (str | None): Optional species hint accepted by MyGene.
            max_workers (int): Maximum number of parallel worker threads.
            batch_size (int): Number of identifiers per provider query chunk.

        Returns:
            dict[str, str]: Source identifier to first resolved target identifier.

        Raises:
            ValueError: If source or target identifier namespace is unsupported.
        """

        source_scope = self._SOURCE_SCOPE_BY_ID_TYPE.get(source_id_type)
        target_fields = self._TARGET_FIELDS.get(target_id_type)
        if source_scope is None:
            raise ValueError(f"Unsupported source_id_type: {source_id_type!r}.")
        if target_fields is None:
            raise ValueError(f"Unsupported target_id_type: {target_id_type!r}.")
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1.")
        if max_workers < 1:
            raise ValueError("max_workers must be at least 1.")

        field_string = ",".join(target_fields)
        chunks = [
            list(identifiers[index : index + batch_size])
            for index in range(0, len(identifiers), batch_size)
        ]
        if not chunks:
            return {}

        worker_count = min(max_workers, len(chunks))
        resolved_mapping: dict[str, str] = {}

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [
                executor.submit(
                    self._query_mygene_chunk,
                    chunk,
                    source_scope,
                    field_string,
                    species,
                )
                for chunk in chunks
            ]
            for future in as_completed(futures):
                for hit in future.result():
                    query_identifier = str(hit.get("query", "")).strip()
                    if not query_identifier or query_identifier in resolved_mapping:
                        continue
                    resolved_identifier = self._extract_target_identifier(
                        hit=hit,
                        target_id_type=target_id_type,
                    )
                    if resolved_identifier is None:
                        continue
                    resolved_mapping[query_identifier] = resolved_identifier

        return resolved_mapping

    @staticmethod
    def _query_mygene_chunk(
        chunk: list[str],
        source_scope: str,
        field_string: str,
        species: str | None,
    ) -> list[dict[str, Any]]:
        """Generated: validation needed.

        Description:
            Execute one MyGene querymany call for one identifier chunk.

        Args:
            chunk (list[str]): Identifier chunk.
            source_scope (str): MyGene scopes value.
            field_string (str): MyGene fields value.
            species (str | None): Optional species filter.

        Returns:
            list[dict[str, Any]]: Raw MyGene hits for chunk.
        """

        mygene_client = mygene.MyGeneInfo()
        return mygene_client.querymany(
            chunk,
            scopes=source_scope,
            fields=field_string,
            species=species,
            verbose=False,
        )

    @staticmethod
    def _extract_target_identifier(hit: dict[str, Any], *, target_id_type: str) -> str | None:
        """Generated: validation needed.

        Description:
            Extract one target identifier from one MyGene hit record.

        Args:
            hit (dict[str, Any]): MyGene hit record.
            target_id_type (str): Target namespace selector.

        Returns:
            str | None: First resolved target identifier when available.
        """

        if hit.get("notfound"):
            return None

        if target_id_type == "symbol":
            value = hit.get("symbol")
            return str(value).strip() if isinstance(value, str) and value.strip() else None
        if target_id_type == "entrez_gene_id":
            value = hit.get("entrezgene")
            if value is None:
                return None
            return str(value).strip() or None
        if target_id_type != "ensembl_gene_id":
            return None

        return IdentifierTranslationService._extract_ensembl_gene_identifier(hit)

    @staticmethod
    def _extract_ensembl_gene_identifier(hit: dict[str, Any]) -> str | None:
        """Generated: validation needed.

        Description:
            Extract one Ensembl gene identifier from variant MyGene hit structures.

        Args:
            hit (dict[str, Any]): MyGene hit record.

        Returns:
            str | None: First resolved Ensembl gene identifier.
        """

        candidate_values: list[str] = []

        def append_candidate(value: Any) -> None:
            if isinstance(value, str):
                candidate_values.append(value)
                return
            if isinstance(value, dict):
                append_candidate(value.get("gene"))
                return
            if isinstance(value, list):
                for nested_value in value:
                    append_candidate(nested_value)

        append_candidate(hit.get("ensembl"))
        append_candidate(hit.get("ensemblgene"))
        append_candidate(hit.get("ensembl.gene"))

        for candidate_value in candidate_values:
            normalised_candidate = str(candidate_value).strip()
            if normalised_candidate.upper().startswith("ENS"):
                return normalised_candidate
        return None
