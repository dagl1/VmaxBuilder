"""Generated: validation needed.

Description:
    Identifier translation utilities for expression/model harmonisation and
    transcript-to-gene mapping.
"""

from __future__ import annotations

import ast
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

import mygene
import pandas as pd
import requests

from VmaxBuilder.utils.lookup_cache import LookupCache, get_default_cache_dir


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
        "ensembl_transcript_id": ("ensembl.transcript",),
        "symbol": ("symbol",),
        "entrez_gene_id": ("entrezgene",),
    }

    _SOURCE_SCOPE_BY_ID_TYPE: dict[str, str] = {
        "symbol": "symbol,alias",
        "entrez_gene_id": "entrezgene",
        "ensembl_gene_id": "ensembl.gene,ensemblgene",
        "ensembl_transcript_id": "ensembl.transcript",
    }
    _ENSEMBL_REST_BASE = "https://rest.ensembl.org"

    def __init__(self, logger: Any | None = None) -> None:
        """Generated: validation needed.

        Description:
            Create identifier translation service with optional project logger.

        Args:
            logger (Any | None): Optional logger receiving batch progress updates.

        Modifies:
            self.logger
        """

        self.logger = logger

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

    def build_gene_transcript_dataframe(  # noqa: C901
        self,
        gene_ids: Sequence[str],
        *,
        gene_id_type: str,
        target_type: str = "gene",
        species: str | None = None,
        provider: str = "auto",
        max_workers: int = 8,
        batch_size: int = 500,
        include_sequence_metadata: bool = True,
        include_cdna_sequence: bool = False,
    ) -> pd.DataFrame:
        """Generated: validation needed.

        Description:
            Build transcript metadata table for model genes with transcript-level
            annotation fields used by downstream transcript IFP expansion.

        Args:
            gene_ids (Sequence[str]): Model gene identifiers.
            gene_id_type (str): Gene identifier namespace.
            species (str | None): Optional species hint forwarded to provider.
            provider (str): Translation provider key. Supported values: auto, mygene.
            max_workers (int): Maximum number of parallel worker threads.
            batch_size (int): Number of identifiers per provider query chunk.
            include_sequence_metadata (bool): Whether to enrich transcript rows with
                amino-acid sequence metadata using Ensembl REST lookup.
            include_cdna_sequence (bool): Whether to request cDNA sequence/length in
                addition to amino-acid sequence metadata.

        Returns:
            pd.DataFrame: Transcript metadata table with columns:
                transcript_id, gene_id, is_protein_coding, is_canonical,
                peptide_len, cdna_len, peptide_seq, cdna_seq.

        Raises:
            ValueError: If provider or gene identifier namespace is unsupported.
        """

        deduplicated_gene_ids = self._deduplicate_identifiers(gene_ids)
        if not deduplicated_gene_ids:
            return pd.DataFrame(
                columns=[
                    "transcript_id",
                    "gene_id",
                    "is_protein_coding",
                    "is_canonical",
                    "translation_id",
                    "peptide_len",
                    "cdna_len",
                    "peptide_seq",
                    "cdna_seq",
                ]
            )

        source_scope = self._SOURCE_SCOPE_BY_ID_TYPE.get(gene_id_type)
        if source_scope is None:
            raise ValueError(f"Unsupported gene_id_type: {gene_id_type!r}.")
        if provider not in {"auto", "mygene"}:
            raise ValueError("provider must be 'auto' or 'mygene'.")
        if provider == "auto":
            provider = "mygene"
        if provider != "mygene":
            raise ValueError("Unsupported provider.")

        fields = (
            "ensembl.gene,ensembl.transcript,ensembl.translation,"
            "ensembl.canonical_transcript,type_of_gene"
        )
        chunks = [
            list(deduplicated_gene_ids[index : index + batch_size])
            for index in range(0, len(deduplicated_gene_ids), batch_size)
        ]
        if not chunks:
            return pd.DataFrame(
                columns=[
                    "transcript_id",
                    "gene_id",
                    "is_protein_coding",
                    "is_canonical",
                    "translation_id",
                    "peptide_len",
                    "cdna_len",
                    "peptide_seq",
                    "cdna_seq",
                ]
            )

        worker_count = min(max_workers, len(chunks))
        rows: list[dict[str, Any]] = []
        self._report_progress_start(
            batch_name="mygene_transcript_metadata",
            total_items=len(chunks),
        )
        completed_chunks = 0
        next_percent_threshold = 10

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [
                executor.submit(
                    self._query_mygene_chunk,
                    chunk,
                    source_scope,
                    fields,
                    species,
                )
                for chunk in chunks
            ]
            for future in as_completed(futures):
                for hit in future.result():
                    rows.extend(self._extract_transcript_rows_from_hit(hit))
                completed_chunks += 1
                next_percent_threshold = self._report_progress_tick(
                    batch_name="mygene_transcript_metadata",
                    completed_items=completed_chunks,
                    total_items=len(chunks),
                    next_percent_threshold=next_percent_threshold,
                )

        transcript_df = pd.DataFrame(
            rows,
            columns=[
                "transcript_id",
                "gene_id",
                "is_protein_coding",
                "is_canonical",
                "translation_id",
                "peptide_len",
                "cdna_len",
                "peptide_seq",
                "cdna_seq",
            ],
        )
        if transcript_df.empty:
            return transcript_df
        transcript_df = transcript_df.dropna(subset=["transcript_id", "gene_id"])
        transcript_df["transcript_id"] = transcript_df["transcript_id"].astype(str)
        transcript_df["gene_id"] = transcript_df["gene_id"].astype(str)
        transcript_df = transcript_df.drop_duplicates(subset=["transcript_id", "gene_id"])
        if include_sequence_metadata:
            transcript_df = self.enrich_transcript_dataframe_with_sequences(
                transcript_df,
                include_cdna_sequence=include_cdna_sequence,
                max_workers=max_workers,
            )
        return transcript_df.reset_index(drop=True)

    def enrich_transcript_dataframe_with_sequences(  # noqa: C901
        self,
        transcript_df: pd.DataFrame,
        *,
        include_cdna_sequence: bool = False,
        max_workers: int = 8,
    ) -> pd.DataFrame:
        """Generated: validation needed.

        Description:
            Enrich transcript metadata rows with amino-acid sequence information,
            lengths, and optional cDNA sequence metadata using Ensembl REST.

        Args:
            transcript_df (pd.DataFrame): Transcript metadata dataframe containing
                transcript_id column.
            include_cdna_sequence (bool): Whether cDNA sequence/length should be fetched.
            max_workers (int): Maximum number of worker threads for Ensembl requests.

        Returns:
            pd.DataFrame: Enriched transcript dataframe.
        """

        if transcript_df.empty or "transcript_id" not in transcript_df.columns:
            return transcript_df

        enriched_transcript_df = self._explode_transcript_identifier_rows(
            transcript_df.copy()
        )
        if enriched_transcript_df.empty:
            return enriched_transcript_df

        for column in [
            "translation_id",
            "peptide_seq",
            "peptide_len",
            "cdna_seq",
            "cdna_len",
        ]:
            if column not in enriched_transcript_df.columns:
                enriched_transcript_df[column] = None

        cache = LookupCache(get_default_cache_dir(), "ensembl_transcript_sequences")
        transcript_ids = [
            transcript_id
            for transcript_id in enriched_transcript_df["transcript_id"].dropna().unique()
            if isinstance(transcript_id, str) and transcript_id.strip()
        ]
        if not transcript_ids:
            return enriched_transcript_df

        fetched_rows = self._fetch_transcript_sequence_rows(
            transcript_ids,
            include_cdna_sequence=include_cdna_sequence,
            max_workers=max_workers,
            cache=cache,
        )

        if not fetched_rows:
            return enriched_transcript_df

        lookup = {row["transcript_id"]: row for row in fetched_rows}

        for row_index, transcript_id in enriched_transcript_df["transcript_id"].items():
            transcript_key = str(transcript_id)
            fetched = lookup.get(transcript_key)
            if fetched is None:
                continue
            for column in [
                "translation_id",
                "peptide_seq",
                "peptide_len",
                "cdna_seq",
                "cdna_len",
            ]:
                current_value = enriched_transcript_df.at[row_index, column]
                if pd.isna(current_value) or current_value in (None, ""):
                    enriched_transcript_df.at[row_index, column] = fetched.get(column)

            peptide_seq = enriched_transcript_df.at[row_index, "peptide_seq"]
            peptide_len = enriched_transcript_df.at[row_index, "peptide_len"]
            if (pd.isna(peptide_len) or peptide_len in (None, "")) and isinstance(
                peptide_seq, str
            ):
                enriched_transcript_df.at[row_index, "peptide_len"] = len(peptide_seq)

            cdna_seq = enriched_transcript_df.at[row_index, "cdna_seq"]
            cdna_len = enriched_transcript_df.at[row_index, "cdna_len"]
            if (pd.isna(cdna_len) or cdna_len in (None, "")) and isinstance(cdna_seq, str):
                enriched_transcript_df.at[row_index, "cdna_len"] = len(cdna_seq)

        return enriched_transcript_df

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

    @staticmethod
    def _normalise_transcript_identifiers(value: Any) -> list[str]:
        """Generated: validation needed.

        Description:
            Normalize transcript identifier payload into flat list of transcript IDs.

        Args:
            value (Any): Raw transcript identifier payload from dataframe or API.

        Returns:
            list[str]: Parsed transcript identifiers.
        """

        if value is None:
            return []
        if isinstance(value, str):
            stripped_value = value.strip()
            if not stripped_value:
                return []
            if stripped_value.startswith("[") and stripped_value.endswith("]"):
                try:
                    parsed_value = ast.literal_eval(stripped_value)
                except (SyntaxError, ValueError):
                    return [stripped_value]
                return IdentifierTranslationService._normalise_transcript_identifiers(
                    parsed_value
                )
            return [stripped_value]
        if isinstance(value, (list, tuple, set)):
            identifiers: list[str] = []
            for nested_value in value:
                identifiers.extend(
                    IdentifierTranslationService._normalise_transcript_identifiers(
                        nested_value
                    )
                )
            return list(dict.fromkeys(identifier for identifier in identifiers if identifier))
        return [str(value).strip()] if str(value).strip() else []

    def _explode_transcript_identifier_rows(
        self, transcript_df: pd.DataFrame
    ) -> pd.DataFrame:
        """Generated: validation needed.

        Description:
            Expand rows containing multiple transcript identifiers into one row per
            transcript identifier.

        Args:
            transcript_df (pd.DataFrame): Transcript metadata dataframe with
                transcript_id column.

        Returns:
            pd.DataFrame: Dataframe with normalized single transcript_id per row.
        """

        if transcript_df.empty or "transcript_id" not in transcript_df.columns:
            return transcript_df

        exploded_rows: list[dict[str, Any]] = []
        for _, row in transcript_df.iterrows():
            row_dict = row.to_dict()
            transcript_ids = self._normalise_transcript_identifiers(
                row_dict.get("transcript_id")
            )
            if not transcript_ids:
                continue
            for transcript_id in transcript_ids:
                new_row = dict(row_dict)
                new_row["transcript_id"] = transcript_id
                exploded_rows.append(new_row)

        if not exploded_rows:
            return pd.DataFrame(columns=transcript_df.columns)
        exploded_df = pd.DataFrame(exploded_rows)
        return exploded_df.drop_duplicates().reset_index(drop=True)

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

    def _fetch_canonical_transcript_id(
        self,
        gene_id: str,
    ) -> str | None:
        normalised_gene_id = gene_id.split(".")[0]

        lookup_url = f"{self._ENSEMBL_REST_BASE}/lookup/id/{normalised_gene_id}?expand=1"

        lookup_record = self._ensembl_get_json(lookup_url)

        if not isinstance(lookup_record, dict):
            return None

        canonical = lookup_record.get("canonical_transcript")

        if isinstance(canonical, str) and canonical.strip():
            return canonical.strip()

        return None

    def _extract_transcript_rows_from_hit(  # noqa: C901
        self, hit: dict[str, Any], target_type: str = "gene"
    ) -> list[dict[str, Any]]:
        """Generated: validation needed.

        Description:
            Extract transcript metadata rows from one MyGene hit payload.

        Args:
            hit (dict[str, Any]): MyGene hit record.

        Returns:
            list[dict[str, Any]]: Transcript metadata rows.
        """

        if hit.get("notfound"):
            return []

        canonical_transcript = self._extract_canonical_transcript_identifier(hit)
        gene_is_protein_coding = str(hit.get("type_of_gene", "")).lower() == "protein-coding"
        fallback_gene_id = self._extract_ensembl_gene_identifier(hit)

        transcript_rows: list[dict[str, Any]] = []
        ensembl_payload = hit.get("ensembl")
        entries: list[dict[str, Any]] = []
        if isinstance(ensembl_payload, dict):
            entries = [ensembl_payload]
        elif isinstance(ensembl_payload, list):
            entries = [entry for entry in ensembl_payload if isinstance(entry, dict)]

        for entry in entries:
            transcript_ids = self._normalise_transcript_identifiers(entry.get("transcript"))
            gene_id = entry.get("gene") or fallback_gene_id
            canonical_transcript = self._fetch_canonical_transcript_id(gene_id)
            print(f"Canonical transcript for gene_id {gene_id}: {canonical_transcript}")
            # normalise canonical_transcript
            canonical_transcript = (
                canonical_transcript.split(".")[0] if canonical_transcript else None
            )

            translation_payload = entry.get("translation")
            translation_id = None
            if isinstance(translation_payload, str):
                translation_id = translation_payload
            elif isinstance(translation_payload, dict):
                translation_id = translation_payload.get("id")

            peptide_seq = entry.get("peptide_seq")
            cdna_seq = entry.get("cdna_seq")
            peptide_len = entry.get("peptide_len")
            cdna_len = entry.get("cdna_len")
            if peptide_len is None and isinstance(peptide_seq, str):
                peptide_len = len(peptide_seq)
            if cdna_len is None and isinstance(cdna_seq, str):
                cdna_len = len(cdna_seq)

            for transcript_id in transcript_ids:
                if target_type == "gene" and canonical_transcript != transcript_id:
                    continue
                transcript_rows.append(
                    {
                        "transcript_id": str(transcript_id),
                        "gene_id": str(gene_id),
                        "is_protein_coding": bool(gene_is_protein_coding),
                        "is_canonical": bool(
                            canonical_transcript is not None
                            and str(transcript_id) == canonical_transcript
                        ),
                        "translation_id": translation_id,
                        "peptide_len": peptide_len,
                        "cdna_len": cdna_len,
                        "peptide_seq": peptide_seq,
                        "cdna_seq": cdna_seq,
                    }
                )

        return transcript_rows

    @staticmethod
    def _extract_canonical_transcript_identifier(hit: dict[str, Any]) -> str | None:
        """Generated: validation needed.

        Description:
            Extract canonical transcript identifier from one MyGene hit payload.

        Args:
            hit (dict[str, Any]): MyGene hit record.

        Returns:
            str | None: Canonical transcript identifier when available.
        """

        candidates: list[Any] = [
            hit.get("ensembl.canonical_transcript"),
            hit.get("canonical_transcript"),
        ]
        ensembl_payload = hit.get("ensembl")
        if isinstance(ensembl_payload, dict):
            candidates.append(ensembl_payload.get("canonical_transcript"))

        for candidate in candidates:
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return None

    def _fetch_transcript_sequence_rows(
        self,
        transcript_ids: list[str],
        *,
        include_cdna_sequence: bool,
        max_workers: int,
        cache: LookupCache,
    ) -> list[dict[str, Any]]:
        """Generated: validation needed.

        Description:
            Fetch transcript sequence metadata through cache-aware threaded Ensembl
            REST lookups.

        Args:
            transcript_ids (list[str]): Transcript identifiers to resolve.
            include_cdna_sequence (bool): Whether to request cDNA sequence.
            max_workers (int): Maximum number of worker threads.
            cache (LookupCache): Disk-backed lookup cache.

        Returns:
            list[dict[str, Any]]: Sequence metadata rows keyed by transcript_id.
        """

        cached_rows: list[dict[str, Any]] = []
        missing_transcript_ids: list[str] = []
        cache_suffix = "with_cdna" if include_cdna_sequence else "aa_only"

        for transcript_id in transcript_ids:
            cache_key = f"{transcript_id}:{cache_suffix}"
            cached_entry = cache.get(cache_key)
            if isinstance(cached_entry, dict):
                cached_rows.append(cached_entry)
            else:
                missing_transcript_ids.append(transcript_id)

        if missing_transcript_ids:
            self._report_progress_start(
                batch_name="ensembl_transcript_sequence_lookup",
                total_items=len(missing_transcript_ids),
            )
            worker_count = max(1, min(max_workers, len(missing_transcript_ids)))
            completed_items = 0
            next_percent_threshold = 10
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                futures = {
                    executor.submit(
                        self._fetch_single_transcript_sequence_row,
                        transcript_id,
                        include_cdna_sequence=include_cdna_sequence,
                    ): transcript_id
                    for transcript_id in missing_transcript_ids
                }

                for future in as_completed(futures):
                    transcript_id = futures[future]
                    fetched_row = future.result()
                    cache_key = f"{transcript_id}:{cache_suffix}"
                    cache.set(cache_key, fetched_row)
                    cached_rows.append(fetched_row)
                    completed_items += 1
                    next_percent_threshold = self._report_progress_tick(
                        batch_name="ensembl_transcript_sequence_lookup",
                        completed_items=completed_items,
                        total_items=len(missing_transcript_ids),
                        next_percent_threshold=next_percent_threshold,
                    )

        return cached_rows

    def _fetch_single_transcript_sequence_row_with_retry(
        self,
        transcript_id: str,
        *,
        include_cdna_sequence: bool,
        max_retries: int = 4,
        retry_delay: float = 1.0,
    ) -> dict[str, Any]:
        _last_error: Exception | None = None

        for attempt in range(max_retries):
            try:
                result = self._fetch_single_transcript_sequence_row(
                    transcript_id,
                    include_cdna_sequence=include_cdna_sequence,
                )

                # Don't accept an empty protein lookup as a successful result.
                if result.get("peptide_seq"):
                    return result

                if result.get("translation_id"):
                    return result

                raise RuntimeError(
                    f"No translation/protein sequence returned for {transcript_id}"
                )

            except Exception as exc:
                _last_error = exc

                if attempt < max_retries - 1:
                    delay = retry_delay * (2**attempt)
                    time.sleep(delay)

    def _fetch_single_transcript_sequence_row(
        self,
        transcript_id: str,
        *,
        include_cdna_sequence: bool,
    ) -> dict[str, Any]:
        """Generated: validation needed.

        Description:
            Fetch sequence metadata for one transcript from Ensembl REST.

        Args:
            transcript_id (str): Ensembl transcript identifier.
            include_cdna_sequence (bool): Whether to request cDNA sequence.

        Returns:
            dict[str, Any]: Sequence metadata payload for transcript.
        """

        normalised_transcript_id = transcript_id.split(".")[0]
        lookup_url = (
            f"{self._ENSEMBL_REST_BASE}/lookup/id/{normalised_transcript_id}?expand=1"
        )
        lookup_record = self._ensembl_get_json(lookup_url)

        translation_id = None
        if isinstance(lookup_record, dict):
            translation_payload = lookup_record.get("Translation")
            if isinstance(translation_payload, dict):
                translation_id = translation_payload.get("id")

        peptide_seq = None
        if translation_id:
            protein_url = (
                f"{self._ENSEMBL_REST_BASE}/sequence/id/{translation_id}?type=protein"
            )
            protein_record = self._ensembl_get_json(protein_url)
            if isinstance(protein_record, dict):
                peptide_seq = protein_record.get("seq")

        cdna_seq = None
        if include_cdna_sequence:
            cdna_url = (
                f"{self._ENSEMBL_REST_BASE}/sequence/id/{normalised_transcript_id}?type=cdna"
            )
            cdna_record = self._ensembl_get_json(cdna_url)
            if isinstance(cdna_record, dict):
                cdna_seq = cdna_record.get("seq")

        return {
            "transcript_id": transcript_id,
            "translation_id": translation_id,
            "peptide_seq": peptide_seq,
            "peptide_len": len(peptide_seq) if isinstance(peptide_seq, str) else None,
            "cdna_seq": cdna_seq,
            "cdna_len": len(cdna_seq) if isinstance(cdna_seq, str) else None,
        }

    @staticmethod
    def _ensembl_get_json(
        url: str,
        retries: int = 3,
        timeout: int = 30,
    ) -> dict[str, Any] | None:
        """Generated: validation needed.

        Description:
            Execute GET request against Ensembl REST API with retry behaviour.

        Args:
            url (str): Request URL.
            retries (int): Maximum number of attempts.
            timeout (int): Request timeout in seconds.

        Returns:
            dict[str, Any] | None: Parsed JSON payload when successful.
        """

        headers = {"Accept": "application/json"}
        for _ in range(max(1, retries)):
            try:
                response = requests.get(url, headers=headers, timeout=timeout)
            except requests.RequestException:
                continue

            if response.status_code == 429:
                continue
            if response.ok:
                try:
                    payload = response.json()
                except ValueError:
                    return None
                if isinstance(payload, dict):
                    return payload
                return None
        return None

    def _report_progress_start(self, *, batch_name: str, total_items: int) -> None:
        """Generated: validation needed.

        Description:
            Emit progress start message for long-running lookup batches.

        Args:
            batch_name (str): Batch identifier.
            total_items (int): Number of queued items.

        Requires:
            self.logger: Optional logger receiving progress updates.
        """

        message = f"Starting {batch_name}: {total_items} items"
        if self.logger is not None:
            self.logger.info(message, print_level=2)
            return
        print(message)

    def _report_progress_tick(
        self,
        batch_name: str,
        *,
        completed_items: int,
        total_items: int,
        next_percent_threshold: int,
    ) -> int:
        """Generated: validation needed.

        Description:
            Emit 10-percent progress updates and return next threshold.

        Args:
            batch_name (str): Batch identifier.
            completed_items (int): Number of completed items.
            total_items (int): Number of queued items.
            next_percent_threshold (int): Next percentage milestone.

        Requires:
            self.logger: Optional logger receiving progress updates.

        Returns:
            int: Updated percentage milestone.
        """

        if total_items < 1:
            return 100

        progress_percent = int((completed_items / total_items) * 100)
        milestone_percent = min(100, (progress_percent // 10) * 10)
        if milestone_percent >= next_percent_threshold:
            message = f"{batch_name}: {milestone_percent}% ({completed_items}/{total_items})"
            if self.logger is not None:
                self.logger.info(message, print_level=2)
            else:
                print(message)
            next_percent_threshold = milestone_percent + 10
        return next_percent_threshold
