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

# todo: revisit this as overall sequence lookup is very slow, could probably be a lot faster
# add intermediate saving in case of long lookups and a crash


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
    _TRANSCRIPT_METADATA_COLUMNS: list[str] = [
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

    def __init__(self, logger: Any | None = None) -> None:
        """Generated: validation needed.

        Description:
            Create identifier translation service with optional project logger.

        Args:
            logger (Any | None): Optional logger receiving batch progress updates.

        Modifies:
            self.logger
            self.last_sequence_lookup_summary
        """

        self.logger = logger
        self.last_sequence_lookup_summary = self._empty_sequence_lookup_summary()

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
            target_type (str): Retrieval mode. "gene" returns canonical transcript per
                gene; "transcript" returns all protein-coding transcripts.
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
            ValueError: If provider, target type, or gene identifier namespace is unsupported.
        """

        deduplicated_gene_ids = self._deduplicate_identifiers(gene_ids)
        if not deduplicated_gene_ids:
            return pd.DataFrame(columns=self._TRANSCRIPT_METADATA_COLUMNS)

        if target_type not in {"gene", "transcript"}:
            raise ValueError("target_type must be 'gene' or 'transcript'.")
        self.last_sequence_lookup_summary = self._empty_sequence_lookup_summary()

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
            return pd.DataFrame(columns=self._TRANSCRIPT_METADATA_COLUMNS)

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
                    queried_gene_id = str(hit.get("query", "")).strip()

                    if not queried_gene_id:
                        continue
                    rows.extend(
                        self._extract_transcript_rows_from_hit(
                            hit, query_gene_id=queried_gene_id, target_type=target_type
                        )
                    )
                completed_chunks += 1
                next_percent_threshold = self._report_progress_tick(
                    batch_name="mygene_transcript_metadata",
                    completed_items=completed_chunks,
                    total_items=len(chunks),
                    next_percent_threshold=next_percent_threshold,
                )

        transcript_df = pd.DataFrame(
            rows,
            columns=self._TRANSCRIPT_METADATA_COLUMNS,
        )
        if transcript_df.empty:
            return transcript_df
        transcript_df = transcript_df.dropna(subset=["transcript_id", "gene_id"])
        transcript_df["transcript_id"] = (
            transcript_df["transcript_id"].astype(str).map(self._normalise_identifier_version)
        )
        transcript_df["gene_id"] = transcript_df["gene_id"].astype(str)
        transcript_df = self._filter_transcript_rows_for_target_type(
            transcript_df,
            target_type,
        )
        transcript_df = transcript_df.drop_duplicates(subset=["transcript_id", "gene_id"])
        if include_sequence_metadata:
            transcript_df = self.enrich_transcript_dataframe_with_sequences(
                transcript_df,
                include_cdna_sequence=include_cdna_sequence,
                max_workers=max_workers,
            )
            transcript_df = self._filter_transcript_rows_for_target_type(
                transcript_df,
                target_type,
                require_resolved_protein=True,
            )
            transcript_df = self._finalise_transcript_flags(
                transcript_df,
                target_type=target_type,
            )
        else:
            self.last_sequence_lookup_summary = self._build_sequence_flag_summary(
                transcript_df,
                target_type=target_type,
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
        """Execute one MyGene querymany call for one identifier chunk."""

        mygene_client = mygene.MyGeneInfo()

        result = mygene_client.querymany(
            chunk,
            scopes=source_scope,
            fields=field_string,
            species=species,
            verbose=False,
        )

        return result

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

    def _extract_transcript_rows_from_hit(  # noqa: C901
        self,
        hit: dict[str, Any],
        query_gene_id: str,
        target_type: str = "gene",
    ) -> list[dict[str, Any]]:
        """Extract transcript metadata rows from one MyGene hit payload."""

        if hit.get("notfound"):
            return []

        canonical_transcript = self._normalise_identifier_version(
            self._extract_canonical_transcript_identifier(hit)
        )
        fallback_gene_id = self._extract_ensembl_gene_identifier(hit)

        transcript_rows: list[dict[str, Any]] = []

        ensembl_payload = hit.get("ensembl")

        entries: list[dict[str, Any]] = []

        if isinstance(ensembl_payload, dict):
            entries = [ensembl_payload]
        elif isinstance(ensembl_payload, list):
            entries = [entry for entry in ensembl_payload if isinstance(entry, dict)]

        normalised_query_gene_id = str(query_gene_id).split(".")[0] if query_gene_id else ""

        matching_entries = [
            entry
            for entry in entries
            if str(entry.get("gene", "")).split(".")[0] == normalised_query_gene_id
        ]

        # Prefer an exact match. If MyGene did not return one, preserve
        # the previous fallback behaviour.
        entries_to_process = matching_entries or entries

        for entry in entries_to_process:
            transcript_ids = [
                self._normalise_identifier_version(transcript_id)
                for transcript_id in self._normalise_transcript_identifiers(
                    entry.get("transcript")
                )
            ]

            transcript_ids = self._deduplicate_identifiers(transcript_ids)

            # The queried identifier is authoritative.
            gene_id = query_gene_id or entry.get("gene") or fallback_gene_id

            translation_payload = entry.get("translation")

            translation_id = None

            if isinstance(translation_payload, str):
                translation_id = translation_payload

            elif isinstance(translation_payload, dict):
                translation_id = translation_payload.get("id")

            has_translation = isinstance(translation_id, str) and bool(translation_id.strip())

            peptide_seq = entry.get("peptide_seq")
            cdna_seq = entry.get("cdna_seq")

            peptide_len = entry.get("peptide_len")
            cdna_len = entry.get("cdna_len")

            if peptide_len is None and isinstance(peptide_seq, str):
                peptide_len = len(peptide_seq)

            if cdna_len is None and isinstance(cdna_seq, str):
                cdna_len = len(cdna_seq)

            for transcript_id in transcript_ids:
                transcript_rows.append(
                    {
                        "transcript_id": str(transcript_id),
                        "gene_id": str(gene_id),
                        "is_protein_coding": bool(has_translation),
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

        if target_type != "gene":
            return transcript_rows

        if not transcript_rows:
            return []

        if canonical_transcript is not None:
            canonical_rows = [
                row
                for row in transcript_rows
                if self._normalise_identifier_version(row["transcript_id"])
                == canonical_transcript
            ]

            if canonical_rows:
                if canonical_rows[0]["is_protein_coding"]:
                    return [canonical_rows[0]]

        protein_coding_rows = [
            row for row in transcript_rows if bool(row.get("is_protein_coding"))
        ]

        if protein_coding_rows:
            fallback_row = dict(protein_coding_rows[0])
            fallback_row["is_canonical"] = False
            return [fallback_row]

        if canonical_transcript is not None:
            canonical_rows = [
                row
                for row in transcript_rows
                if self._normalise_identifier_version(row["transcript_id"])
                == canonical_transcript
            ]

            if canonical_rows:
                return [canonical_rows[0]]

        return [transcript_rows[0]]

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

    def _fetch_transcript_sequence_rows(  # noqa: C901
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

        cached_rows_by_transcript: dict[str, dict[str, Any]] = {}
        missing_transcript_ids: list[str] = []
        cache_suffix = "with_cdna" if include_cdna_sequence else "aa_only"

        for transcript_id in transcript_ids:
            cache_key = f"{transcript_id}:{cache_suffix}"
            cached_entry = cache.get(cache_key)
            if isinstance(cached_entry, dict) and self._is_sequence_row_usable(cached_entry):
                cached_rows_by_transcript[transcript_id] = cached_entry
            else:
                if isinstance(cached_entry, dict):
                    cache.invalidate(cache_key)
                missing_transcript_ids.append(transcript_id)

        fetched_rows_by_transcript: dict[str, dict[str, Any]] = {}
        unresolved_transcript_ids = missing_transcript_ids

        if unresolved_transcript_ids:
            self._report_progress_start(
                batch_name="ensembl_transcript_sequence_lookup",
                total_items=len(unresolved_transcript_ids),
            )
            worker_count = max(1, min(max_workers, len(unresolved_transcript_ids)))

            def fetch_rows(
                pending_transcript_ids: list[str],
                *,
                batch_name: str,
                max_retries: int,
            ) -> tuple[dict[str, dict[str, Any]], list[str], list[str]]:
                resolved_rows: dict[str, dict[str, Any]] = {}
                unresolved_ids: list[str] = []
                non_protein_coding_ids: list[str] = []
                with ThreadPoolExecutor(max_workers=worker_count) as executor:
                    futures = {
                        executor.submit(
                            self._fetch_single_transcript_sequence_row_with_retry,
                            transcript_id,
                            include_cdna_sequence=include_cdna_sequence,
                            max_retries=max_retries,
                        ): transcript_id
                        for transcript_id in pending_transcript_ids
                    }

                    local_completed_items = 0
                    local_next_percent_threshold = 10
                    for future in as_completed(futures):
                        transcript_id = futures[future]
                        fetched_row = future.result()
                        if self._is_sequence_row_usable(fetched_row):
                            resolved_rows[transcript_id] = fetched_row
                        elif fetched_row.get("status") == "non_protein_coding":
                            non_protein_coding_ids.append(transcript_id)
                        else:
                            unresolved_ids.append(transcript_id)

                        local_completed_items += 1
                        local_next_percent_threshold = self._report_progress_tick(
                            batch_name=batch_name,
                            completed_items=local_completed_items,
                            total_items=len(pending_transcript_ids),
                            next_percent_threshold=local_next_percent_threshold,
                        )
                return resolved_rows, unresolved_ids, non_protein_coding_ids

            (
                first_pass_rows,
                unresolved_transcript_ids,
                non_protein_coding_ids,
            ) = fetch_rows(
                unresolved_transcript_ids,
                batch_name="ensembl_transcript_sequence_lookup",
                max_retries=3,
            )
            fetched_rows_by_transcript.update(first_pass_rows)

            if unresolved_transcript_ids:
                self._report_progress_start(
                    batch_name="ensembl_transcript_sequence_retry",
                    total_items=len(unresolved_transcript_ids),
                )
                (
                    retry_rows,
                    unresolved_transcript_ids,
                    retry_non_protein_coding_ids,
                ) = fetch_rows(
                    unresolved_transcript_ids,
                    batch_name="ensembl_transcript_sequence_retry",
                    max_retries=5,
                )
                fetched_rows_by_transcript.update(retry_rows)
                non_protein_coding_ids.extend(retry_non_protein_coding_ids)

            if non_protein_coding_ids:
                non_protein_coding_count = len(set(non_protein_coding_ids))
                self._report_progress_info(
                    "ensembl_transcript_sequence_lookup: "
                    f"skipped {non_protein_coding_count} non-protein-coding transcripts"
                )

            if unresolved_transcript_ids:
                unresolved_count = len(set(unresolved_transcript_ids))
                unresolved_examples = ", ".join(sorted(set(unresolved_transcript_ids))[:5])
                self._report_progress_warning(
                    "ensembl_transcript_sequence_lookup: "
                    f"unresolved {unresolved_count} transcripts after retry "
                    f"(examples: {unresolved_examples})"
                )

            resolved_count = len(fetched_rows_by_transcript)
            total_count = len(transcript_ids)
            self._report_progress_info(
                "ensembl_transcript_sequence_lookup: "
                f"resolved {resolved_count} / {total_count} transcripts"
            )

            for transcript_id, fetched_row in fetched_rows_by_transcript.items():
                cache_key = f"{transcript_id}:{cache_suffix}"
                cache.set(cache_key, fetched_row)

        merged_rows = dict(cached_rows_by_transcript)
        merged_rows.update(fetched_rows_by_transcript)
        return list(merged_rows.values())

    def _fetch_single_transcript_sequence_row_with_retry(
        self,
        transcript_id: str,
        *,
        include_cdna_sequence: bool,
        max_retries: int = 4,
        retry_delay: float = 1.0,
    ) -> dict[str, Any]:
        """Generated: validation needed.

        Description:
            Fetch transcript sequence metadata with exponential-backoff retries and
            return best-effort payload on persistent failures.

        Args:
            transcript_id (str): Ensembl transcript identifier.
            include_cdna_sequence (bool): Whether to request cDNA sequence.
            max_retries (int): Maximum number of fetch attempts.
            retry_delay (float): Base retry delay in seconds.

        Returns:
            dict[str, Any]: Sequence metadata payload for transcript.
        """

        _last_error: Exception | None = None

        for attempt in range(max_retries):
            try:
                result = self._fetch_single_transcript_sequence_row(
                    transcript_id,
                    include_cdna_sequence=include_cdna_sequence,
                )

                if result.get("status") == "non_protein_coding":
                    return result

                # Don't accept an empty protein lookup as a successful result.
                if result.get("peptide_seq"):
                    return result

                raise RuntimeError(
                    f"No translation/protein sequence returned for {transcript_id}"
                )

            except Exception as exc:
                _last_error = exc

                if attempt < max_retries - 1:
                    delay = retry_delay * (2**attempt)
                    time.sleep(delay)

        if _last_error is not None:
            _ = _last_error

        return {
            "transcript_id": transcript_id,
            "translation_id": None,
            "peptide_seq": None,
            "peptide_len": None,
            "cdna_seq": None,
            "cdna_len": None,
        }

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
        transcript_parent_gene_id = None
        transcript_biotype = None
        if isinstance(lookup_record, dict):
            translation_payload = lookup_record.get("Translation")
            if isinstance(translation_payload, dict):
                translation_id = translation_payload.get("id")
            transcript_parent_gene_id = lookup_record.get("Parent")
            transcript_biotype = lookup_record.get("biotype")

        translation_id, peptide_seq = self._resolve_transcript_protein_sequence(
            transcript_id=normalised_transcript_id,
            translation_id=translation_id,
        )

        if (
            self._is_non_protein_coding_biotype(transcript_biotype)
            and (not isinstance(peptide_seq, str) or not peptide_seq.strip())
            and isinstance(transcript_parent_gene_id, str)
            and transcript_parent_gene_id.strip()
        ):
            fallback_translation_id, fallback_peptide_seq = (
                self._resolve_gene_level_fallback_protein_sequence(transcript_parent_gene_id)
            )
            if isinstance(fallback_peptide_seq, str) and fallback_peptide_seq.strip():
                translation_id = fallback_translation_id
                peptide_seq = fallback_peptide_seq

        if self._is_non_protein_coding_biotype(transcript_biotype) and (
            not isinstance(peptide_seq, str) or not peptide_seq.strip()
        ):
            return {
                "transcript_id": transcript_id,
                "translation_id": None,
                "peptide_seq": None,
                "peptide_len": None,
                "cdna_seq": None,
                "cdna_len": None,
                "status": "non_protein_coding",
            }

        if (
            (not isinstance(peptide_seq, str) or not peptide_seq.strip())
            and isinstance(transcript_parent_gene_id, str)
            and transcript_parent_gene_id.strip()
        ):
            fallback_translation_id, fallback_peptide_seq = (
                self._resolve_gene_level_fallback_protein_sequence(transcript_parent_gene_id)
            )
            if isinstance(fallback_peptide_seq, str) and fallback_peptide_seq.strip():
                translation_id = fallback_translation_id
                peptide_seq = fallback_peptide_seq

        cdna_seq = None
        if include_cdna_sequence:
            cdna_url = (
                f"{self._ENSEMBL_REST_BASE}/sequence/id/{normalised_transcript_id}?type=cdna"
            )
            cdna_record = self._ensembl_get_json(cdna_url)
            if isinstance(cdna_record, dict):
                cdna_seq = cdna_record.get("seq")

        resolved_status = (
            "resolved"
            if isinstance(peptide_seq, str) and peptide_seq.strip()
            else "unresolved"
        )
        return {
            "transcript_id": transcript_id,
            "translation_id": translation_id,
            "peptide_seq": peptide_seq,
            "peptide_len": len(peptide_seq) if isinstance(peptide_seq, str) else None,
            "cdna_seq": cdna_seq,
            "cdna_len": len(cdna_seq) if isinstance(cdna_seq, str) else None,
            "status": resolved_status,
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
        for attempt in range(max(1, retries)):
            try:
                response = requests.get(url, headers=headers, timeout=timeout)
            except requests.RequestException:
                if attempt < max(1, retries) - 1:
                    time.sleep(0.5 * (2**attempt))
                continue

            if response.status_code == 429:
                if attempt < max(1, retries) - 1:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after and retry_after.isdigit():
                        time.sleep(float(retry_after))
                    else:
                        time.sleep(0.5 * (2**attempt))
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

    @staticmethod
    def _normalise_identifier_version(identifier: str | None) -> str | None:
        """Generated: validation needed.

        Description:
            Remove version suffix from Ensembl-like identifier values.

        Args:
            identifier (str | None): Raw identifier value.

        Returns:
            str | None: Identifier without version suffix.
        """

        if not isinstance(identifier, str):
            return None
        stripped_identifier = identifier.strip()
        if not stripped_identifier:
            return None
        return stripped_identifier.split(".")[0]

    def _filter_transcript_rows_for_target_type(
        self,
        transcript_df: pd.DataFrame,
        target_type: str,
        *,
        require_resolved_protein: bool = False,
    ) -> pd.DataFrame:
        """Generated: validation needed.

        Description:
            Filter transcript metadata rows to requested target granularity.

        Args:
            transcript_df (pd.DataFrame): Transcript metadata table.
            target_type (str): Target retrieval mode, gene or transcript.
            require_resolved_protein (bool): Whether rows must include resolved
                protein sequence metadata.

        Returns:
            pd.DataFrame: Filtered transcript metadata table.
        """

        if transcript_df.empty:
            return transcript_df

        filtered_transcript_df = transcript_df.copy()
        if target_type == "gene":
            if "is_canonical" in filtered_transcript_df.columns:
                canonical_mask = filtered_transcript_df["is_canonical"].fillna(False)
                canonical_rows = filtered_transcript_df.loc[canonical_mask]
                if not canonical_rows.empty:
                    filtered_transcript_df = canonical_rows
            filtered_transcript_df = filtered_transcript_df.drop_duplicates(
                subset=["gene_id"]
            )

        if target_type == "transcript":
            pass

        if require_resolved_protein:
            peptide_mask = filtered_transcript_df["peptide_seq"].apply(
                lambda value: isinstance(value, str) and bool(value.strip())
            )
            filtered_transcript_df = filtered_transcript_df.loc[peptide_mask]

        return filtered_transcript_df

    def _finalise_transcript_flags(
        self,
        transcript_df: pd.DataFrame,
        *,
        target_type: str,
    ) -> pd.DataFrame:
        """Generated: validation needed.

        Description:
            Reconcile transcript annotation flags with resolved sequence evidence.

        Args:
            transcript_df (pd.DataFrame): Transcript metadata table.
            target_type (str): Target retrieval mode, gene or transcript.

        Returns:
            pd.DataFrame: Transcript metadata table with updated flags.
        """

        if transcript_df.empty:
            self.last_sequence_lookup_summary = self._empty_sequence_lookup_summary()
            return transcript_df

        finalised_transcript_df = transcript_df.copy()
        if "is_protein_coding" not in finalised_transcript_df.columns:
            finalised_transcript_df["is_protein_coding"] = False
        if "is_canonical" not in finalised_transcript_df.columns:
            finalised_transcript_df["is_canonical"] = False

        initial_protein_coding_mask = finalised_transcript_df["is_protein_coding"].fillna(
            False
        )
        initial_canonical_mask = finalised_transcript_df["is_canonical"].fillna(False)

        peptide_mask = finalised_transcript_df["peptide_seq"].apply(
            lambda value: isinstance(value, str) and bool(value.strip())
        )
        finalised_transcript_df.loc[peptide_mask, "is_protein_coding"] = True

        if target_type == "gene":
            # In gene mode we emit one selected representative AA sequence per gene.
            finalised_transcript_df.loc[peptide_mask, "is_canonical"] = True

        self.last_sequence_lookup_summary = self._build_sequence_flag_summary(
            finalised_transcript_df,
            target_type=target_type,
            initial_protein_coding_mask=initial_protein_coding_mask,
            initial_canonical_mask=initial_canonical_mask,
        )

        return finalised_transcript_df

    @staticmethod
    def _empty_sequence_lookup_summary() -> dict[str, int | str]:
        """Generated: validation needed.

        Description:
            Build default sequence-lookup diagnostics payload.

        Returns:
            dict[str, int | str]: Empty diagnostics summary.
        """

        return {
            "target_type": "unknown",
            "rows_with_sequence_evidence": 0,
            "protein_coding_flags_corrected": 0,
            "canonical_flags_corrected": 0,
            "flags_corrected_from_sequence_evidence": 0,
        }

    @staticmethod
    def _build_sequence_flag_summary(
        transcript_df: pd.DataFrame,
        *,
        target_type: str,
        initial_protein_coding_mask: pd.Series | None = None,
        initial_canonical_mask: pd.Series | None = None,
    ) -> dict[str, int | str]:
        """Generated: validation needed.

        Description:
            Build diagnostics describing annotation flag corrections driven by
            resolved amino-acid sequence evidence.

        Args:
            transcript_df (pd.DataFrame): Transcript metadata table.
            target_type (str): Target retrieval mode, gene or transcript.
            initial_protein_coding_mask (pd.Series | None): Optional pre-correction
                protein-coding flags.
            initial_canonical_mask (pd.Series | None): Optional pre-correction
                canonical flags.

        Returns:
            dict[str, int | str]: Diagnostics summary for sequence-based corrections.
        """

        if transcript_df.empty:
            return {
                "target_type": target_type,
                "rows_with_sequence_evidence": 0,
                "protein_coding_flags_corrected": 0,
                "canonical_flags_corrected": 0,
                "flags_corrected_from_sequence_evidence": 0,
            }

        peptide_mask = transcript_df["peptide_seq"].apply(
            lambda value: isinstance(value, str) and bool(value.strip())
        )
        if initial_protein_coding_mask is None:
            initial_protein_coding_mask = transcript_df["is_protein_coding"].fillna(False)
        if initial_canonical_mask is None:
            initial_canonical_mask = transcript_df["is_canonical"].fillna(False)

        protein_coding_flags_corrected = int(
            (peptide_mask & ~initial_protein_coding_mask).sum()
        )
        canonical_flags_corrected = 0
        if target_type == "gene":
            canonical_flags_corrected = int((peptide_mask & ~initial_canonical_mask).sum())

        return {
            "target_type": target_type,
            "rows_with_sequence_evidence": int(peptide_mask.sum()),
            "protein_coding_flags_corrected": protein_coding_flags_corrected,
            "canonical_flags_corrected": canonical_flags_corrected,
            "flags_corrected_from_sequence_evidence": (
                protein_coding_flags_corrected + canonical_flags_corrected
            ),
        }

    @staticmethod
    def _is_sequence_row_usable(sequence_row: dict[str, Any]) -> bool:
        """Generated: validation needed.

        Description:
            Validate transcript sequence payload for downstream use and caching.

        Args:
            sequence_row (dict[str, Any]): Sequence metadata payload.

        Returns:
            bool: True when amino-acid sequence is present.
        """

        peptide_seq = sequence_row.get("peptide_seq")
        return isinstance(peptide_seq, str) and bool(peptide_seq.strip())

    def _resolve_transcript_protein_sequence(
        self,
        *,
        transcript_id: str,
        translation_id: str | None,
    ) -> tuple[str | None, str | None]:
        """Generated: validation needed.

        Description:
            Resolve protein sequence from Ensembl translation endpoint and fall back
            to transcript protein endpoint when necessary.

        Args:
            transcript_id (str): Normalised Ensembl transcript identifier.
            translation_id (str | None): Translation identifier from transcript lookup.

        Returns:
            tuple[str | None, str | None]: Resolved translation identifier and peptide
                sequence.
        """

        peptide_seq: str | None = None
        resolved_translation_id = translation_id

        if resolved_translation_id:
            protein_url = (
                f"{self._ENSEMBL_REST_BASE}/sequence"
                f"/id/{resolved_translation_id}?type=protein"
            )
            protein_record = self._ensembl_get_json(protein_url)
            if isinstance(protein_record, dict):
                candidate_sequence = protein_record.get("seq")
                if isinstance(candidate_sequence, str) and candidate_sequence.strip():
                    peptide_seq = candidate_sequence

        if peptide_seq:
            return resolved_translation_id, peptide_seq

        transcript_protein_url = (
            f"{self._ENSEMBL_REST_BASE}/sequence/id/{transcript_id}?type=protein"
        )
        transcript_protein_record = self._ensembl_get_json(transcript_protein_url)
        if isinstance(transcript_protein_record, dict):
            candidate_sequence = transcript_protein_record.get("seq")
            if isinstance(candidate_sequence, str) and candidate_sequence.strip():
                peptide_seq = candidate_sequence
            if not resolved_translation_id:
                candidate_translation_id = transcript_protein_record.get("id")
                if isinstance(candidate_translation_id, str) and candidate_translation_id:
                    resolved_translation_id = candidate_translation_id

        return resolved_translation_id, peptide_seq

    def _report_progress_warning(self, message: str) -> None:
        """Generated: validation needed.

        Description:
            Emit warning message through logger when available, otherwise stdout.

        Args:
            message (str): Warning text.

        Requires:
            self.logger: Optional logger receiving progress updates.
        """

        if self.logger is not None:
            self.logger.warning(message, print_level=2)
            return
        print(message)

    def _report_progress_info(self, message: str) -> None:
        """Generated: validation needed.

        Description:
            Emit info message through logger when available, otherwise stdout.

        Args:
            message (str): Info text.

        Requires:
            self.logger: Optional logger receiving progress updates.
        """

        if self.logger is not None:
            self.logger.info(message, print_level=2)
            return
        print(message)

    @staticmethod
    def _is_non_protein_coding_biotype(biotype: Any) -> bool:
        """Generated: validation needed.

        Description:
            Determine whether Ensembl transcript biotype is non-protein-coding.

        Args:
            biotype (Any): Transcript biotype value from Ensembl lookup payload.

        Returns:
            bool: True when biotype clearly indicates non-protein-coding transcript.
        """

        if not isinstance(biotype, str) or not biotype.strip():
            return False
        normalised_biotype = biotype.strip().lower().replace("-", "_")
        return normalised_biotype != "protein_coding"

    def _resolve_gene_level_fallback_protein_sequence(  # noqa: C901
        self,
        parent_gene_id: str,
    ) -> tuple[str | None, str | None]:
        """Generated: validation needed.

        Description:
            Resolve fallback protein sequence from parent gene when requested
            transcript has no protein sequence.

        Args:
            parent_gene_id (str): Parent Ensembl gene identifier.

        Returns:
            tuple[str | None, str | None]: Fallback translation identifier and
                peptide sequence.
        """

        normalised_gene_id = parent_gene_id.split(".")[0]
        lookup_url = f"{self._ENSEMBL_REST_BASE}/lookup/id/{normalised_gene_id}?expand=1"
        gene_lookup_record = self._ensembl_get_json(lookup_url)
        if not isinstance(gene_lookup_record, dict):
            return None, None

        transcript_payload = gene_lookup_record.get("Transcript")
        if not isinstance(transcript_payload, list):
            return None, None

        candidate_entries: list[dict[str, Any]] = [
            entry for entry in transcript_payload if isinstance(entry, dict)
        ]
        if not candidate_entries:
            return None, None

        canonical_transcript_id = self._normalise_identifier_version(
            gene_lookup_record.get("canonical_transcript")
        )
        protein_candidates: list[tuple[str, str | None, bool]] = []
        for entry in candidate_entries:
            transcript_id = self._normalise_identifier_version(entry.get("id"))
            if transcript_id is None:
                continue
            if self._is_non_protein_coding_biotype(entry.get("biotype")):
                continue
            translation_payload = entry.get("Translation")
            translation_id = None
            if isinstance(translation_payload, dict):
                translation_id = translation_payload.get("id")
            is_canonical = transcript_id == canonical_transcript_id
            protein_candidates.append((transcript_id, translation_id, is_canonical))

        if not protein_candidates:
            return None, None

        ordered_candidates = sorted(
            protein_candidates,
            key=lambda candidate: (not candidate[2], candidate[0]),
        )
        for fallback_transcript_id, fallback_translation_id, _ in ordered_candidates:
            resolved_translation_id, peptide_seq = self._resolve_transcript_protein_sequence(
                transcript_id=fallback_transcript_id,
                translation_id=fallback_translation_id,
            )
            if isinstance(peptide_seq, str) and peptide_seq.strip():
                return resolved_translation_id, peptide_seq
        return None, None

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
