# ruff: noqa: E501, C901, B007
from __future__ import annotations

import csv
import re
import time
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
from cobra.core.model import Model
from pubchempy import PubChemHTTPError, get_compounds
from rdkit import Chem, RDLogger

from VmaxBuilder.utils.extra_utils import remove_compartment
from VmaxBuilder.utils.lookup_cache import (
    LookupCache,
    get_default_cache_dir,
    smiles_cache_key,
)

RDLogger.DisableLog("rdApp.*")  # ty: ignore [unresolved-attribute]
DEFAULT_SMILES_LENGTH_LIMIT = 218
DEFAULT_PUBCHEM_NAMESPACE = "name"
PUBCHEM_QUERY_CACHE_NAMESPACE = "smiles_pubchem_queries"
PUBCHEM_CID_CACHE_NAMESPACE = "smiles_pubchem_cids"
EXPECTED_MANUAL_SMILES_COLUMNS = [
    "name",
    "id",
    "id_without_compartment",
    "base_to_work_from",
    "difference",
    "base_smiles",
    "modified_smiles",
]
SMILES_OUTPUT_COLUMNS = [
    "name",
    "id",
    "id_without_compartment",
    "formula",
    "InChI",
    "InChIKey",
    "isomeric_SMILES",
    "canonical_SMILES",
    "isomeric SMILES",
    "canonical SMILES",
    "source",
    "source_query",
    "source_identifier",
    "missing_smiles",
    "smiles_longer_than_218",
]
_SUFFIX_REPLACEMENTS: dict[str, tuple[str, ...]] = {
    "nate": ("nic acid", "nic-acid", "nic Acid", "nic-Acid"),
    "ide": ("ic acid", "ic-acid", "ic Acid", "ic-Acid"),
    "_form": ("",),
    " form": ("",),
    "form": ("",),
    "ate": ("ic acid", "ic-acid", "ic Acid", "ic-Acid"),
    "ic": ("ic acid", "ic-acid", "ic Acid", "ic-Acid"),
}
_OYL_PATTERN = re.compile(
    (
        r"oyl(?:coa|CoA|ACP|"
        r"-coa|-ACP|-CoA| Coenzyme A|-Coenzyme A|-\[ACP\]| ACP| \[ACP\])?$"
    ),
    re.IGNORECASE,
)
_COA_FRAGMENT = (
    "SCCNC(=O)CCNC(=O)C(C(C)(C)COP(=O)(O)OP(=O)(O)OCC1C(C(C(O1)"
    "N2C=NC3=C(N=CN=C32)N)O)OP(=O)(O)O)O"
)
_ACP_FRAGMENT = "S"
_ACP_FROM_COA_PATTERN = re.compile(r"SCCNC\(=O\)CCNC\(=O\)C\(C\(C\)\(C\)CO.*")
_PROTONATION_PATTERN = re.compile(
    r"^(?P<base>.*?)(?:H(?P<hydrogen>\d+))?(?P<suffix>[+-]\d+)?$"
)


@dataclass(slots=True)
class PubChemCandidate:
    """Generated: validation needed.

    Description:
        Normalised PubChem compound payload used by SMILES retrieval helpers.

    Args:
        compound_id (str | None): PubChem compound identifier.
        query (str): Query string used to obtain candidate.
        search_namespace (str): PubChem namespace used during lookup.
        isomeric_smiles (str | None): Isomeric SMILES string.
        canonical_smiles (str | None): Canonical SMILES string.
        inchi (str | None): InChI string.
        inchikey (str | None): InChIKey string.
        iupac_name (str | None): IUPAC name.
        molecular_formula (str | None): Molecular formula reported by PubChem.
    """

    compound_id: str | None
    query: str | int
    search_namespace: str
    isomeric_smiles: str | None = None
    canonical_smiles: str | None = None
    inchi: str | None = None
    inchikey: str | None = None
    iupac_name: str | None = None
    molecular_formula: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Generated: validation needed.

        Description:
            Convert candidate into JSON-safe dictionary for disk cache persistence.

        Returns:
            dict[str, Any]: Serialized candidate payload.
        """

        return {
            "compound_id": self.compound_id,
            "query": self.query,
            "search_namespace": self.search_namespace,
            "isomeric_smiles": self.isomeric_smiles,
            "canonical_smiles": self.canonical_smiles,
            "inchi": self.inchi,
            "inchikey": self.inchikey,
            "iupac_name": self.iupac_name,
            "molecular_formula": self.molecular_formula,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PubChemCandidate":
        """Generated: validation needed.

        Description:
            Reconstruct candidate from cached dictionary payload.

        Args:
            data (dict[str, Any]): Serialized candidate payload.

        Returns:
            PubChemCandidate: Reconstructed candidate instance.
        """

        return cls(
            compound_id=_normalise_optional_string(data.get("compound_id")),
            query=str(data.get("query", "")),
            search_namespace=str(data.get("search_namespace", DEFAULT_PUBCHEM_NAMESPACE)),
            isomeric_smiles=_normalise_optional_string(data.get("isomeric_smiles")),
            canonical_smiles=_normalise_optional_string(data.get("canonical_smiles")),
            inchi=_normalise_optional_string(data.get("inchi")),
            inchikey=_normalise_optional_string(data.get("inchikey")),
            iupac_name=_normalise_optional_string(data.get("iupac_name")),
            molecular_formula=_normalise_optional_string(data.get("molecular_formula")),
        )


@dataclass(slots=True)
class SmilesGenerationResult:
    """Generated: validation needed.

    Description:
        Bundles SMILES retrieval outputs, diagnostics, and metadata.

    Args:
        smiles_df (pd.DataFrame): Final metabolite-level SMILES table.
        summary (dict[str, Any]): Compact run summary.
        diagnostics (dict[str, Any]): Detailed diagnostics payload.
        metadata (dict[str, Any]): Reproducibility metadata.
    """

    smiles_df: pd.DataFrame
    summary: dict[str, Any]
    diagnostics: dict[str, Any]
    metadata: dict[str, Any]


@dataclass(slots=True)
class _MetaboliteRecord:
    """Generated: validation needed.

    Description:
        Internal metabolite representation for one no-compartment metabolite.

    Args:
        metabolite_id (str): Compartment-free metabolite identifier.
        name (str): Representative metabolite name.
        formula (str | None): Representative formula.
        source_model_ids (list[str]): Model metabolite identifiers collapsed into this record.
    """

    metabolite_id: str
    name: str
    formula: str | None
    source_model_ids: list[str] = field(default_factory=list)


def _normalise_optional_string(value: Any) -> str | None:
    """Generated: validation needed.

    Description:
        Convert scalar into stripped string, mapping blank and NA-like values to None.

    Args:
        value (Any): Scalar value to normalise.

    Returns:
        str | None: Normalised string or None.
    """

    if value is None:
        return None
    if isinstance(value, str):
        stripped_value = value.strip()
        if not stripped_value or stripped_value.lower() == "nan":
            return None
        return stripped_value
    if pd.isna(value):
        return None
    string_value = str(value).strip()
    if not string_value or string_value.lower() == "nan":
        return None
    return string_value


def _normalise_metabolite_identifier(metabolite_id: Any) -> Any:
    """Generated: validation needed.

    Description:
        Remove common compartment suffix patterns from metabolite identifiers while
        preserving existing project-specific normalisation.

    Args:
        metabolite_id (Any): Identifier to normalise.

    Returns:
        Any: Compartment-free metabolite identifier when pattern matches.
    """

    normalised_identifier = remove_compartment(metabolite_id)
    if not isinstance(normalised_identifier, str):
        return normalised_identifier
    bracket_match = re.match(r"^(?P<base>.+)\[[A-Za-z0-9_]+]$", normalised_identifier)
    if bracket_match is not None:
        return bracket_match.group("base")
    suffix_match = re.match(r"^(?P<base>.+)_[A-Za-z0-9]+$", normalised_identifier)
    if suffix_match is not None:
        return suffix_match.group("base")
    return normalised_identifier


def inchi_to_smiles(inchi: Any, *, isomeric: bool = True) -> str | None:
    """Generated: validation needed.

    Description:
        Convert InChI string into RDKit-derived SMILES string.

    Args:
        inchi (Any): InChI-like scalar value.
        isomeric (bool): Whether to request isomeric SMILES output.

    Returns:
        str | None: Converted SMILES string, or None when conversion fails.
    """

    normalised_inchi = _normalise_optional_string(inchi)
    if normalised_inchi is None:
        return None
    molecule = Chem.MolFromInchi(normalised_inchi)
    if molecule is None:
        return None
    return Chem.MolToSmiles(molecule, isomericSmiles=isomeric)


def smiles_to_inchi(smiles: Any) -> str | None:
    """Generated: validation needed.

    Description:
        Convert SMILES string into RDKit-derived InChI string.

    Args:
        smiles (Any): SMILES-like scalar value.

    Returns:
        str | None: Converted InChI string, or None when conversion fails.
    """

    normalised_smiles = _normalise_optional_string(smiles)
    if normalised_smiles is None:
        return None
    molecule = Chem.MolFromSmiles(normalised_smiles)
    if molecule is None:
        return None
    return Chem.MolToInchi(molecule)


def load_model_data_frame(location: str | Path) -> pd.DataFrame:
    """Generated: validation needed.

    Description:
        Load model metadata table, preferring `METS` sheet for spreadsheet inputs.

    Args:
        location (str | Path): File path to model metadata table.

    Returns:
        pd.DataFrame: Loaded model metadata dataframe.
    """

    path = Path(location)
    if path.suffix.lower() == ".xlsx":
        workbook = pd.ExcelFile(path)
        for sheet_name in ("METS", "mets", "Metabolites"):
            if sheet_name in workbook.sheet_names:
                return workbook.parse(sheet_name=sheet_name)
        return workbook.parse(sheet_name=workbook.sheet_names[0])
    if path.suffix.lower() == ".tsv":
        return pd.read_csv(path, sep="\t")
    return pd.read_csv(path)


def load_manually_curated_smiles_file(location: str | Path) -> pd.DataFrame:
    """Generated: validation needed.

    Description:
        Load manual SMILES corrections, recovering rows with unquoted commas in names.

    Args:
        location (str | Path): File path to manual SMILES corrections table.

    Returns:
        pd.DataFrame: Parsed manual corrections dataframe.
    """

    path = Path(location)
    file_lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    if not file_lines:
        return pd.DataFrame(columns=EXPECTED_MANUAL_SMILES_COLUMNS)

    header_line = file_lines[0]
    delimiter = "\t" if "\t" in header_line else ","
    parsed_header = [column.strip() for column in header_line.split(delimiter)]
    if parsed_header == EXPECTED_MANUAL_SMILES_COLUMNS:
        rows: list[list[str | None]] = []
    else:
        try:
            parsed_dataframe = pd.read_csv(path, sep=delimiter, dtype=str)
            if set(EXPECTED_MANUAL_SMILES_COLUMNS).issubset(parsed_dataframe.columns):
                return parsed_dataframe[EXPECTED_MANUAL_SMILES_COLUMNS].reset_index(drop=True)
        except Exception:
            pass

    rows: list[list[str | None]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        next(reader, None)
        for row in reader:
            if not row:
                continue
            if len(row) > len(EXPECTED_MANUAL_SMILES_COLUMNS):
                extra_fields = len(row) - len(EXPECTED_MANUAL_SMILES_COLUMNS) + 1
                name = delimiter.join(row[:extra_fields])
                row = [name, *row[extra_fields:]]
            row += [None] * (len(EXPECTED_MANUAL_SMILES_COLUMNS) - len(row))
            rows.append(row[: len(EXPECTED_MANUAL_SMILES_COLUMNS)])
    return pd.DataFrame(rows, columns=EXPECTED_MANUAL_SMILES_COLUMNS).reset_index(drop=True)


def function_for_identifying_novel_found_SMILES_and_only_doing_those(
    old_SMILES_df: pd.DataFrame,
    new_SMILES_df: pd.DataFrame,
) -> pd.DataFrame:
    """Generated: validation needed.

    Description:
        Return metabolite rows that still need fresh SMILES resolution work.

    Args:
        old_SMILES_df (pd.DataFrame): Existing SMILES table from previous run.
        new_SMILES_df (pd.DataFrame): Newly constructed metabolite table for current model.

    Returns:
        pd.DataFrame: Subset of current table requiring new lookup work.
    """

    if old_SMILES_df.empty:
        return new_SMILES_df.copy()

    previous_smiles_df = old_SMILES_df.copy()
    if "id_without_compartment" not in previous_smiles_df.columns:
        if "id" not in previous_smiles_df.columns:
            return new_SMILES_df.copy()
        previous_smiles_df["id_without_compartment"] = previous_smiles_df["id"].map(
            _normalise_metabolite_identifier
        )

    smile_columns = [
        column_name
        for column_name in (
            "isomeric_SMILES",
            "canonical_SMILES",
            "isomeric SMILES",
            "canonical SMILES",
        )
        if column_name in previous_smiles_df.columns
    ]
    if not smile_columns:
        return new_SMILES_df.copy()

    resolved_previous_ids = set(
        previous_smiles_df.loc[
            previous_smiles_df[smile_columns].notna().any(axis=1),
            "id_without_compartment",
        ].astype(str)
    )
    return new_SMILES_df.loc[
        ~new_SMILES_df["id_without_compartment"].astype(str).isin(resolved_previous_ids)
    ].reset_index(drop=True)


class PubChemLookupService:
    """Generated: validation needed.

    Description:
        Execute cached, threaded PubChem lookups for names and CIDs.

    Args:
        cache_dir (Path | None): Optional cache directory override.
        max_workers (int): Maximum worker threads for batched lookups.
        retry_attempts (int): Number of retry attempts per request.
        retry_sleep_seconds (float): Sleep duration between retries.
    """

    def __init__(
        self,
        *,
        cache_dir: Path | None = None,
        max_workers: int = 5,
        retry_attempts: int = 3,
        retry_sleep_seconds: float = 3,
    ) -> None:
        self.cache_dir = cache_dir or get_default_cache_dir()
        self.max_workers = max_workers
        self.retry_attempts = retry_attempts
        self.retry_sleep_seconds = retry_sleep_seconds
        self.query_cache = LookupCache(self.cache_dir, PUBCHEM_QUERY_CACHE_NAMESPACE)
        self.cid_cache = LookupCache(self.cache_dir, PUBCHEM_CID_CACHE_NAMESPACE)

    def fetch_candidates(
        self, query_names: Sequence[str]
    ) -> dict[str, list[PubChemCandidate]]:
        """Generated: validation needed.

        Description:
            Fetch PubChem candidates for query names, reusing disk cache when available.

        Args:
            query_names (Sequence[str]): Query names to search in PubChem.

        Returns:
            dict[str, list[PubChemCandidate]]: Query name to candidate list mapping.
        """

        unique_query_names = list(
            dict.fromkeys(query_name for query_name in query_names if query_name)
        )
        if not unique_query_names:
            return {}

        results: dict[str, list[PubChemCandidate]] = {}
        queries_to_fetch: list[str] = []
        for query_name in unique_query_names:
            cache_key = smiles_cache_key("pubchem_name", query_name.casefold())
            cached_payload = self.query_cache.get(cache_key)
            if isinstance(cached_payload, list):
                results[query_name] = [
                    PubChemCandidate.from_dict(candidate_payload)
                    for candidate_payload in cached_payload
                    if isinstance(candidate_payload, dict)
                ]
            else:
                queries_to_fetch.append(query_name)

        if not queries_to_fetch:
            return results

        worker_count = min(self.max_workers, len(queries_to_fetch))
        cached_items: dict[str, list[dict[str, Any]]] = {}
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(self._fetch_name_candidates_uncached, query_name): query_name
                for query_name in queries_to_fetch
            }
            for future in as_completed(futures):
                query_name = futures[future]
                candidates = future.result()
                results[query_name] = candidates
                cached_items[smiles_cache_key("pubchem_name", query_name.casefold())] = [
                    candidate.to_dict() for candidate in candidates
                ]

        if cached_items:
            self.query_cache.set_many(cached_items)
        return results

    def fetch_candidates_by_cid(
        self, compound_ids: Sequence[str]
    ) -> dict[str, list[PubChemCandidate]]:
        """Generated: validation needed.

        Description:
            Fetch PubChem candidates for PubChem compound identifiers.

        Args:
            compound_ids (Sequence[str]): Compound identifiers to query.

        Returns:
            dict[str, list[PubChemCandidate]]: PubChem CID to candidate list mapping.
        """

        unique_compound_ids = list(
            dict.fromkeys(compound_id for compound_id in compound_ids if compound_id)
        )
        if not unique_compound_ids:
            return {}

        results: dict[str, list[PubChemCandidate]] = {}
        compound_ids_to_fetch: list[str] = []
        for compound_id in unique_compound_ids:
            cache_key = smiles_cache_key("pubchem_cid", compound_id)
            cached_payload = self.cid_cache.get(cache_key)
            if isinstance(cached_payload, list):
                results[compound_id] = [
                    PubChemCandidate.from_dict(candidate_payload)
                    for candidate_payload in cached_payload
                    if isinstance(candidate_payload, dict)
                ]
            else:
                compound_ids_to_fetch.append(compound_id)

        if not compound_ids_to_fetch:
            return results

        worker_count = min(self.max_workers, len(compound_ids_to_fetch))
        cached_items: dict[str, list[dict[str, Any]]] = {}
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(self._fetch_cid_candidates_uncached, compound_id): compound_id
                for compound_id in compound_ids_to_fetch
            }
            for future in as_completed(futures):
                compound_id = futures[future]
                candidates = future.result()
                results[compound_id] = candidates
                cached_items[smiles_cache_key("pubchem_cid", compound_id)] = [
                    candidate.to_dict() for candidate in candidates
                ]

        if cached_items:
            self.cid_cache.set_many(cached_items)
        return results

    def _fetch_name_candidates_uncached(self, query_name: str) -> list[PubChemCandidate]:
        """Generated: validation needed.

        Description:
            Query PubChem by metabolite name without consulting cache.

        Args:
            query_name (str): Query name.

        Returns:
            list[PubChemCandidate]: Candidate compounds returned by PubChem.
        """

        print(f"Fetching PubChem candidates for name: {query_name}")
        compounds = self._query_pubchem(query_name, namespace=DEFAULT_PUBCHEM_NAMESPACE)
        return [
            self._compound_to_candidate(compound, query_name, DEFAULT_PUBCHEM_NAMESPACE)
            for compound in compounds
        ]

    def _fetch_cid_candidates_uncached(self, compound_id: str) -> list[PubChemCandidate]:
        """Generated: validation needed.

        Description:
            Query PubChem by CID without consulting cache.

        Args:
            compound_id (str): PubChem CID.

        Returns:
            list[PubChemCandidate]: Candidate compounds returned by PubChem.
        """

        print(f"Fetching PubChem candidates for CID: {compound_id}")
        # requires to be int
        compound_id_int = int(float(compound_id))
        compounds = self._query_pubchem(compound_id_int, namespace="cid")
        return [
            self._compound_to_candidate(compound, compound_id_int, "cid")
            for compound in compounds
        ]

    def _query_pubchem(self, query_value, namespace):
        time.sleep(0.3)

        for attempt in range(self.retry_attempts):
            try:
                return list(get_compounds(query_value, namespace=namespace))
            except (PubChemHTTPError, Exception) as e:
                if attempt < self.retry_attempts - 1:
                    wait_time = self.retry_sleep_seconds * (attempt + 1)
                    time.sleep(wait_time)
                    print(
                        f"Retrying PubChem query for {query_value} "
                        f"in namespace {namespace} "
                        f"(attempt {attempt + 1}/{self.retry_attempts}) after error: {e}"
                    )
                else:
                    print(
                        f"Failed to fetch PubChem candidates for "
                        f"{query_value} in namespace {namespace} after "
                        f"{self.retry_attempts} attempts. Error: {e}"
                    )
                    return []

    @staticmethod
    def _compound_to_candidate(
        compound: Any, query: str | int, search_namespace: str
    ) -> PubChemCandidate:
        """Generated: validation needed.

        Description:
            Convert raw PubChem compound object into normalised candidate dataclass.

        Args:
            compound (Any): Raw PubChem compound object.
            query (str): Original query value.
            search_namespace (str): PubChem namespace used for lookup.

        Returns:
            PubChemCandidate: Normalised candidate.
        """

        return PubChemCandidate(
            compound_id=_normalise_optional_string(getattr(compound, "cid", None)),
            query=query,
            search_namespace=search_namespace,
            isomeric_smiles=_normalise_optional_string(getattr(compound, "smiles", None)),
            canonical_smiles=_normalise_optional_string(
                getattr(compound, "connectivity_smiles", None)
            ),
            inchi=_normalise_optional_string(getattr(compound, "inchi", None)),
            inchikey=_normalise_optional_string(getattr(compound, "inchikey", None)),
            iupac_name=_normalise_optional_string(getattr(compound, "iupac_name", None)),
            molecular_formula=_normalise_optional_string(
                getattr(compound, "molecular_formula", None)
            ),
        )


class SmilesRetrievalService:
    """Generated: validation needed.

    Description:
        Resolve metabolite SMILES from local tables first, then cached threaded PubChem
        lookups.

    Args:
        logger (Any | None): Optional project logger.
        pubchem_lookup_service (PubChemLookupService | None): Optional PubChem service
        override.
        use_most_protonated_smiles (bool): Whether multi-hit PubChem matches prefer most
        protonated formula variant.
        smiles_length_limit (int): Threshold used for UniKP input diagnostics.
    """

    def __init__(
        self,
        *,
        logger: Any | None = None,
        pubchem_lookup_service: PubChemLookupService | None = None,
        use_most_protonated_smiles: bool = True,
        smiles_length_limit: int = DEFAULT_SMILES_LENGTH_LIMIT,
    ) -> None:
        self.logger = logger
        self.pubchem_lookup_service = pubchem_lookup_service or PubChemLookupService()
        self.use_most_protonated_smiles = use_most_protonated_smiles
        self.smiles_length_limit = smiles_length_limit

    def build_smiles_dataframe(
        self,
        *,
        cobra_model: Model,
        existing_smiles_df: pd.DataFrame | None = None,
        model_data_df: pd.DataFrame | None = None,
        metabolites_df: pd.DataFrame | None = None,
        manually_curated_smiles_df: pd.DataFrame | None = None,
        metabolites_smiles_inchi_df: pd.DataFrame | None = None,
        metabolite_name_synonyms_df: pd.DataFrame | None = None,
        chebi_df: pd.DataFrame | None = None,
        chem_prop_df: pd.DataFrame | None = None,
        recon3d_data: dict[str, Any] | list[dict[str, Any]] | None = None,
    ) -> SmilesGenerationResult:
        """Generated: validation needed.

        Description:
            Build final SMILES dataframe for model metabolites using layered local and remote
            sources.

        Args:
            cobra_model (Model): COBRA model containing metabolites and names.
            existing_smiles_df (pd.DataFrame | None): Previously saved SMILES table.
            model_data_df (pd.DataFrame | None): Model metadata table, ideally Human-GEM
            `METS`.
            metabolites_df (pd.DataFrame | None): Human-GEM-style metabolites table.
            manually_curated_smiles_df (pd.DataFrame | None): Manual correction table.
            metabolites_smiles_inchi_df (pd.DataFrame | None): Human-GEM provided
            SMILES/InChI table.
            metabolite_name_synonyms_df (pd.DataFrame | None): Optional synonym table.
            chebi_df (pd.DataFrame | None): ChEBI lookup table with SMILES values.
            chem_prop_df (pd.DataFrame | None): MetaNetX chemistry table.
            recon3d_data (dict[str, Any] | list[dict[str, Any]] | None): Recon3D metabolite
            annotations.

        Returns:
            SmilesGenerationResult: Final dataframe plus diagnostics and metadata.
        """

        metabolite_records = self._build_model_records(cobra_model)
        smiles_df = self._build_base_smiles_dataframe(
            metabolite_records=metabolite_records,
            existing_smiles_df=existing_smiles_df,
        )
        previous_smiles_df = existing_smiles_df
        if previous_smiles_df is None:
            previous_smiles_df = pd.DataFrame()
        lookup_only_df = function_for_identifying_novel_found_SMILES_and_only_doing_those(
            old_SMILES_df=previous_smiles_df,
            new_SMILES_df=smiles_df,
        )
        diagnostics: dict[str, Any] = {
            "new_or_unresolved_metabolites": lookup_only_df[
                "id_without_compartment"
            ].tolist(),
            "conflicts": {},
            "step_counts": {},
        }

        model_data_index = self._build_model_data_index(model_data_df)
        metabolites_index = self._build_metabolites_index(metabolites_df)
        recon3d_index = self._build_recon3d_index(recon3d_data)

        self._apply_inchi_mapping(
            smiles_df=smiles_df,
            inchi_mapping=self._collect_inchi_mapping(
                model_data_index=model_data_index,
                metabolites_smiles_inchi_df=metabolites_smiles_inchi_df,
                manually_curated_smiles_df=manually_curated_smiles_df,
            ),
            source_name="local_inchi",
            diagnostics=diagnostics,
        )
        diagnostics["step_counts"]["after_local_inchi"] = self._count_missing(smiles_df)

        self._apply_smiles_lookup_mapping(
            smiles_df=smiles_df,
            smiles_mapping=self._collect_direct_smiles_mapping(
                metabolites_smiles_inchi_df=metabolites_smiles_inchi_df,
                manually_curated_smiles_df=manually_curated_smiles_df,
            ),
            source_name="local_smiles",
        )
        diagnostics["step_counts"]["after_local_smiles"] = self._count_missing(smiles_df)

        self._apply_database_cross_references(
            smiles_df=smiles_df,
            model_data_index=model_data_index,
            metabolites_index=metabolites_index,
            recon3d_index=recon3d_index,
            chebi_df=chebi_df,
            chem_prop_df=chem_prop_df,
        )
        diagnostics["step_counts"]["after_database_cross_reference"] = self._count_missing(
            smiles_df
        )

        self._apply_pubchem_name_lookups(smiles_df=smiles_df)
        diagnostics["step_counts"]["after_pubchem_name"] = self._count_missing(smiles_df)

        self._apply_synonym_pubchem_lookups(
            smiles_df=smiles_df,
            metabolite_name_synonyms_df=metabolite_name_synonyms_df,
        )
        diagnostics["step_counts"]["after_pubchem_synonyms"] = self._count_missing(smiles_df)

        self._apply_coa_to_acp_fallback(smiles_df)
        diagnostics["step_counts"]["after_coa_acp_fallback"] = self._count_missing(smiles_df)

        final_smiles_df = self._finalise_smiles_dataframe(smiles_df)
        summary = {
            "total_metabolites": int(len(final_smiles_df)),
            "missing_smiles": int(final_smiles_df["missing_smiles"].sum()),
            "smiles_longer_than_218": int(final_smiles_df["smiles_longer_than_218"].sum()),
            "source_counts": dict(
                Counter(
                    source_name
                    for source_name in final_smiles_df["source"].dropna().astype(str)
                    if source_name
                )
            ),
        }
        metadata = {
            "cache_dir": str(self.pubchem_lookup_service.cache_dir),
            "smiles_length_limit": self.smiles_length_limit,
            "use_most_protonated_smiles": self.use_most_protonated_smiles,
        }
        return SmilesGenerationResult(
            smiles_df=final_smiles_df,
            summary=summary,
            diagnostics=diagnostics,
            metadata=metadata,
        )

    def _build_model_records(self, cobra_model: Model) -> dict[str, _MetaboliteRecord]:
        """Generated: validation needed.

        Description:
            Collapse model metabolites to unique compartment-free metabolite records.

        Args:
            cobra_model (Model): COBRA model instance.

        Returns:
            dict[str, _MetaboliteRecord]: Record mapping keyed by no-compartment metabolite
            ID.
        """

        metabolite_records: dict[str, _MetaboliteRecord] = {}
        for metabolite in cobra_model.metabolites:
            metabolite_id = _normalise_metabolite_identifier(metabolite.id)
            if metabolite_id not in metabolite_records:
                metabolite_records[metabolite_id] = _MetaboliteRecord(
                    metabolite_id=metabolite_id,
                    name=str(metabolite.name or metabolite_id),
                    formula=_normalise_optional_string(metabolite.formula),
                    source_model_ids=[metabolite.id],
                )
                continue
            metabolite_records[metabolite_id].source_model_ids.append(metabolite.id)
        return metabolite_records

    def _build_base_smiles_dataframe(
        self,
        *,
        metabolite_records: dict[str, _MetaboliteRecord],
        existing_smiles_df: pd.DataFrame | None,
    ) -> pd.DataFrame:
        """Generated: validation needed.

        Description:
            Build starter SMILES dataframe and merge any existing resolved values.

        Args:
            metabolite_records (dict[str, _MetaboliteRecord]): Model metabolite records.
            existing_smiles_df (pd.DataFrame | None): Previously saved SMILES dataframe.

        Returns:
            pd.DataFrame: Starter dataframe keyed by no-compartment metabolite ID.
        """

        smiles_df = pd.DataFrame(
            [
                {
                    "name": record.name,
                    "id": record.metabolite_id,
                    "id_without_compartment": record.metabolite_id,
                    "formula": record.formula,
                    "InChI": None,
                    "InChIKey": None,
                    "isomeric_SMILES": None,
                    "canonical_SMILES": None,
                    "source": None,
                    "source_query": None,
                    "source_identifier": None,
                }
                for record in metabolite_records.values()
            ]
        )
        if existing_smiles_df is None or existing_smiles_df.empty:
            return smiles_df

        previous_smiles_df = existing_smiles_df.copy()
        if "id_without_compartment" not in previous_smiles_df.columns:
            if "id" in previous_smiles_df.columns:
                previous_smiles_df["id_without_compartment"] = previous_smiles_df["id"].map(
                    _normalise_metabolite_identifier
                )
            else:
                return smiles_df

        for column_name in (
            "InChI",
            "InChIKey",
            "isomeric_SMILES",
            "canonical_SMILES",
            "source",
            "source_query",
            "source_identifier",
        ):
            if column_name not in previous_smiles_df.columns:
                if (
                    column_name == "isomeric_SMILES"
                    and "isomeric SMILES" in previous_smiles_df.columns
                ):
                    previous_smiles_df[column_name] = previous_smiles_df["isomeric SMILES"]
                elif (
                    column_name == "canonical_SMILES"
                    and "canonical SMILES" in previous_smiles_df.columns
                ):
                    previous_smiles_df[column_name] = previous_smiles_df["canonical SMILES"]
                else:
                    previous_smiles_df[column_name] = None

        previous_smiles_df = previous_smiles_df.drop_duplicates(
            subset=["id_without_compartment"],
            keep="first",
        )
        merged_smiles_df = smiles_df.merge(
            previous_smiles_df[
                [
                    "id_without_compartment",
                    "InChI",
                    "InChIKey",
                    "isomeric_SMILES",
                    "canonical_SMILES",
                    "source",
                    "source_query",
                    "source_identifier",
                ]
            ],
            on="id_without_compartment",
            how="left",
            suffixes=("", "_previous"),
        )
        for column_name in (
            "InChI",
            "InChIKey",
            "isomeric_SMILES",
            "canonical_SMILES",
            "source",
            "source_query",
            "source_identifier",
        ):
            previous_column_name = f"{column_name}_previous"
            merged_smiles_df[column_name] = merged_smiles_df[column_name].where(
                merged_smiles_df[column_name].notna(),
                merged_smiles_df[previous_column_name],
            )
            merged_smiles_df = merged_smiles_df.drop(columns=[previous_column_name])
        return merged_smiles_df

    def _build_model_data_index(
        self,
        model_data_df: pd.DataFrame | None,
    ) -> dict[str, dict[str, Any]]:
        """Generated: validation needed.

        Description:
            Index model metadata rows by no-compartment metabolite ID.

        Args:
            model_data_df (pd.DataFrame | None): Model metadata dataframe.

        Returns:
            dict[str, dict[str, Any]]: Indexed row dictionaries.
        """

        if model_data_df is None or model_data_df.empty:
            return {}
        lowered_columns = {
            str(column).strip().lower(): column for column in model_data_df.columns
        }
        identifier_column = lowered_columns.get("id") or lowered_columns.get("replacement id")
        if identifier_column is None:
            return {}
        index: dict[str, dict[str, Any]] = {}
        for _, row in model_data_df.iterrows():
            metabolite_id = _normalise_optional_string(row.get(identifier_column))
            if metabolite_id is None:
                continue
            index[_normalise_metabolite_identifier(metabolite_id)] = row.to_dict()
        return index

    def _build_metabolites_index(
        self,
        metabolites_df: pd.DataFrame | None,
    ) -> dict[str, dict[str, Any]]:
        """Generated: validation needed.

        Description:
            Index Human-GEM-style metabolites table by no-compartment metabolite ID.

        Args:
            metabolites_df (pd.DataFrame | None): Metabolites dataframe.

        Returns:
            dict[str, dict[str, Any]]: Indexed row dictionaries.
        """

        if metabolites_df is None or metabolites_df.empty:
            return {}
        identifier_column = None
        for candidate_column in ("metsNoComp", "mets", "id_without_compartment", "id"):
            if candidate_column in metabolites_df.columns:
                identifier_column = candidate_column
                break
        if identifier_column is None:
            return {}
        index: dict[str, dict[str, Any]] = {}
        for _, row in metabolites_df.iterrows():
            metabolite_id = _normalise_optional_string(row.get(identifier_column))
            if metabolite_id is None:
                continue
            index[_normalise_metabolite_identifier(metabolite_id)] = row.to_dict()
        return index

    def _build_recon3d_index(
        self,
        recon3d_data: dict[str, Any] | list[dict[str, Any]] | None,
    ) -> dict[str, dict[str, Any]]:
        """Generated: validation needed.

        Description:
            Index Recon3D metabolite annotations by compartment-free Recon3D identifier.

        Args:
            recon3d_data (dict[str, Any] | list[dict[str, Any]] | None): Recon3D payload.

        Returns:
            dict[str, dict[str, Any]]: Indexed annotation dictionaries.
        """

        if recon3d_data is None:
            return {}
        metabolites_payload: list[dict[str, Any]]
        if isinstance(recon3d_data, dict):
            candidate_payload = recon3d_data.get("metabolites", [])
            metabolites_payload = [
                entry for entry in candidate_payload if isinstance(entry, dict)
            ]
        elif isinstance(recon3d_data, list):
            metabolites_payload = [entry for entry in recon3d_data if isinstance(entry, dict)]
        else:
            return {}

        index: dict[str, dict[str, Any]] = {}
        for metabolite_entry in metabolites_payload:
            raw_identifier = _normalise_optional_string(metabolite_entry.get("id"))
            if raw_identifier is None:
                continue
            normalised_identifier = _normalise_metabolite_identifier(raw_identifier)
            index[normalised_identifier] = metabolite_entry.get("annotation", {})
        return index

    def _collect_inchi_mapping(
        self,
        *,
        model_data_index: dict[str, dict[str, Any]],
        metabolites_smiles_inchi_df: pd.DataFrame | None,
        manually_curated_smiles_df: pd.DataFrame | None,
    ) -> dict[str, list[tuple[str, str]]]:
        """Generated: validation needed.

        Description:
            Collect InChI candidates from local tables for each metabolite.

        Args:
            model_data_index (dict[str, dict[str, Any]]): Indexed model metadata rows.
            metabolites_smiles_inchi_df (pd.DataFrame | None): Human-GEM SMILES/InChI table.
            manually_curated_smiles_df (pd.DataFrame | None): Manual corrections table.

        Returns:
            dict[str, list[tuple[str, str]]]: Metabolite ID to `(source, inchi)` candidate
            pairs.
        """

        inchi_mapping: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for metabolite_id, row_dict in model_data_index.items():
            for column_name in ("InChI", "inchi"):
                if column_name in row_dict:
                    inchi_value = _normalise_optional_string(row_dict.get(column_name))
                    if inchi_value is not None:
                        inchi_mapping[metabolite_id].append(("model_data", inchi_value))
                        break

        if metabolites_smiles_inchi_df is not None and not metabolites_smiles_inchi_df.empty:
            identifier_column = (
                "metsNoComp"
                if "metsNoComp" in metabolites_smiles_inchi_df.columns
                else "mets"
            )
            if (
                identifier_column in metabolites_smiles_inchi_df.columns
                and "inchi" in metabolites_smiles_inchi_df.columns
            ):
                for _, row in metabolites_smiles_inchi_df.iterrows():
                    metabolite_id = _normalise_optional_string(row.get(identifier_column))
                    inchi_value = _normalise_optional_string(row.get("inchi"))
                    if metabolite_id is None or inchi_value is None:
                        continue
                    inchi_mapping[_normalise_metabolite_identifier(metabolite_id)].append(
                        ("metabolites_SMILES_Inchi", inchi_value)
                    )

        if manually_curated_smiles_df is not None and not manually_curated_smiles_df.empty:
            for _, row in manually_curated_smiles_df.iterrows():
                metabolite_id = _normalise_optional_string(
                    row.get("id_without_compartment") or row.get("id")
                )
                if metabolite_id is None:
                    continue
                inchi_value = smiles_to_inchi(row.get("modified_smiles"))
                if inchi_value is None:
                    continue
                inchi_mapping[_normalise_metabolite_identifier(metabolite_id)].append(
                    ("manually_curated", inchi_value)
                )

        return dict(inchi_mapping)

    def _collect_direct_smiles_mapping(
        self,
        *,
        metabolites_smiles_inchi_df: pd.DataFrame | None,
        manually_curated_smiles_df: pd.DataFrame | None,
    ) -> dict[str, tuple[str, str]]:
        """Generated: validation needed.

        Description:
            Collect direct SMILES candidates from local tables.

        Args:
            metabolites_smiles_inchi_df (pd.DataFrame | None): Human-GEM SMILES/InChI table.
            manually_curated_smiles_df (pd.DataFrame | None): Manual corrections table.

        Returns:
            dict[str, tuple[str, str]]: Metabolite ID to `(source, smiles)` mapping.
        """

        smiles_mapping: dict[str, tuple[str, str]] = {}
        if metabolites_smiles_inchi_df is not None and not metabolites_smiles_inchi_df.empty:
            identifier_column = (
                "metsNoComp"
                if "metsNoComp" in metabolites_smiles_inchi_df.columns
                else "mets"
            )
            if (
                identifier_column in metabolites_smiles_inchi_df.columns
                and "SMILES" in metabolites_smiles_inchi_df.columns
            ):
                for _, row in metabolites_smiles_inchi_df.iterrows():
                    metabolite_id = _normalise_optional_string(row.get(identifier_column))
                    smiles_value = _normalise_optional_string(row.get("SMILES"))
                    if metabolite_id is None or smiles_value is None:
                        continue
                    smiles_mapping.setdefault(
                        _normalise_metabolite_identifier(metabolite_id),
                        ("metabolites_SMILES_Inchi", smiles_value),
                    )

        if manually_curated_smiles_df is not None and not manually_curated_smiles_df.empty:
            for _, row in manually_curated_smiles_df.iterrows():
                metabolite_id = _normalise_optional_string(
                    row.get("id_without_compartment") or row.get("id")
                )
                smiles_value = _normalise_optional_string(row.get("modified_smiles"))
                if metabolite_id is None or smiles_value is None:
                    continue
                smiles_mapping[_normalise_metabolite_identifier(metabolite_id)] = (
                    "manually_curated",
                    smiles_value,
                )
        return smiles_mapping

    def _apply_inchi_mapping(
        self,
        *,
        smiles_df: pd.DataFrame,
        inchi_mapping: dict[str, list[tuple[str, str]]],
        source_name: str,
        diagnostics: dict[str, Any],
    ) -> None:
        """Generated: validation needed.

        Description:
            Resolve SMILES entries from collected InChI candidates and record conflicts.

        Args:
            smiles_df (pd.DataFrame): Working SMILES dataframe.
            inchi_mapping (dict[str, list[tuple[str, str]]]): Collected InChI candidates.
            source_name (str): Source label written into dataframe.
            diagnostics (dict[str, Any]): Mutable diagnostics payload.
        """

        for metabolite_id, source_values in inchi_mapping.items():
            unique_inchis = list(
                dict.fromkeys(inchi_value for _, inchi_value in source_values)
            )
            if not unique_inchis:
                continue
            if len(unique_inchis) > 1:
                diagnostics.setdefault("conflicts", {})[metabolite_id] = {
                    "inchi_candidates": [
                        {"source": source, "inchi": inchi_value}
                        for source, inchi_value in source_values
                    ]
                }
            selected_inchi = unique_inchis[0]
            self._apply_inchi_to_row(
                smiles_df=smiles_df,
                metabolite_id=metabolite_id,
                inchi_value=selected_inchi,
                source_name=source_name,
                source_identifier=selected_inchi,
            )

    def _apply_inchi_to_row(
        self,
        *,
        smiles_df: pd.DataFrame,
        metabolite_id: str,
        inchi_value: str,
        source_name: str,
        source_identifier: str,
    ) -> None:
        """Generated: validation needed.

        Description:
            Populate one dataframe row using one InChI candidate when row is still unresolved.

        Args:
            smiles_df (pd.DataFrame): Working SMILES dataframe.
            metabolite_id (str): Target metabolite ID.
            inchi_value (str): InChI candidate.
            source_name (str): Source label.
            source_identifier (str): Identifier saved for provenance.
        """

        isomeric_smiles = inchi_to_smiles(inchi_value, isomeric=True)
        canonical_smiles = inchi_to_smiles(inchi_value, isomeric=False)
        if isomeric_smiles is None or canonical_smiles is None:
            return
        row_mask = smiles_df["id_without_compartment"] == metabolite_id
        if not bool(row_mask.any()):
            return
        if smiles_df.loc[row_mask, "isomeric_SMILES"].notna().any():
            return
        smiles_df.loc[row_mask, "InChI"] = inchi_value
        smiles_df.loc[row_mask, "isomeric_SMILES"] = isomeric_smiles
        smiles_df.loc[row_mask, "canonical_SMILES"] = canonical_smiles
        smiles_df.loc[row_mask, "source"] = source_name
        smiles_df.loc[row_mask, "source_identifier"] = source_identifier

    def _apply_smiles_lookup_mapping(
        self,
        *,
        smiles_df: pd.DataFrame,
        smiles_mapping: dict[str, tuple[str, str]],
        source_name: str,
    ) -> None:
        """Generated: validation needed.

        Description:
            Populate missing dataframe rows from direct SMILES mappings.

        Args:
            smiles_df (pd.DataFrame): Working SMILES dataframe.
            smiles_mapping (dict[str, tuple[str, str]]): Direct smiles lookup mapping.
            source_name (str): Fallback source label used when mapping entry omits its own
            label.
        """

        for metabolite_id, mapping_value in smiles_mapping.items():
            entry_source_name, smiles_value = mapping_value
            should_overwrite = entry_source_name == "manually_curated"
            self._apply_smiles_to_row(
                smiles_df=smiles_df,
                metabolite_id=metabolite_id,
                smiles_value=smiles_value,
                source_name=entry_source_name or source_name,
                source_identifier=smiles_value,
                source_query=None,
                overwrite=should_overwrite,
            )

    def _apply_smiles_to_row(
        self,
        *,
        smiles_df: pd.DataFrame,
        metabolite_id: str,
        smiles_value: str,
        source_name: str,
        source_identifier: str | None,
        source_query: str | None,
        overwrite: bool = False,
    ) -> None:
        """Generated: validation needed.

        Description:
            Canonicalise and write one SMILES candidate into working dataframe.

        Args:
            smiles_df (pd.DataFrame): Working SMILES dataframe.
            metabolite_id (str): Target metabolite ID.
            smiles_value (str): Candidate smiles string.
            source_name (str): Source label.
            source_identifier (str | None): Source identifier stored for provenance.
            source_query (str | None): Search query stored for provenance.
            overwrite (bool): Whether resolved rows may be overwritten.
        """

        normalised_smiles = _normalise_optional_string(smiles_value)
        if normalised_smiles is None:
            return
        molecule = Chem.MolFromSmiles(normalised_smiles)
        if molecule is None:
            return
        row_mask = smiles_df["id_without_compartment"] == metabolite_id
        if not bool(row_mask.any()):
            return
        if not overwrite and smiles_df.loc[row_mask, "isomeric_SMILES"].notna().any():
            return

        isomeric_smiles = Chem.MolToSmiles(molecule, isomericSmiles=True)
        canonical_smiles = Chem.MolToSmiles(molecule, isomericSmiles=False)
        inchi_value = Chem.MolToInchi(molecule)
        inchi_key = Chem.InchiToInchiKey(inchi_value) if inchi_value else None

        smiles_df.loc[row_mask, "InChI"] = inchi_value
        smiles_df.loc[row_mask, "InChIKey"] = inchi_key
        smiles_df.loc[row_mask, "isomeric_SMILES"] = isomeric_smiles
        smiles_df.loc[row_mask, "canonical_SMILES"] = canonical_smiles
        smiles_df.loc[row_mask, "source"] = source_name
        smiles_df.loc[row_mask, "source_query"] = source_query
        smiles_df.loc[row_mask, "source_identifier"] = source_identifier

    def _apply_database_cross_references(
        self,
        *,
        smiles_df: pd.DataFrame,
        model_data_index: dict[str, dict[str, Any]],
        metabolites_index: dict[str, dict[str, Any]],
        recon3d_index: dict[str, dict[str, Any]],
        chebi_df: pd.DataFrame | None,
        chem_prop_df: pd.DataFrame | None,
    ) -> None:
        """Generated: validation needed.

        Description:
            Resolve missing metabolites from ChEBI, MetaNetX, and PubChem identifiers.

        Args:
            smiles_df (pd.DataFrame): Working SMILES dataframe.
            model_data_index (dict[str, dict[str, Any]]): Indexed model metadata.
            metabolites_index (dict[str, dict[str, Any]]): Indexed metabolites table.
            recon3d_index (dict[str, dict[str, Any]]): Indexed Recon3D annotations.
            chebi_df (pd.DataFrame | None): ChEBI lookup table.
            chem_prop_df (pd.DataFrame | None): MetaNetX chemistry table.
        """

        if smiles_df.empty:
            return

        chebi_mapping = self._build_simple_lookup_mapping(
            chebi_df,
            identifier_column_candidates=("ChEBI ID", "chebi", "CHEBI"),
            smiles_column_candidates=("SMILES", "smiles"),
        )
        metanetx_mapping = self._build_simple_lookup_mapping(
            chem_prop_df,
            identifier_column_candidates=("#ID", "ID", "id"),
            smiles_column_candidates=("SMILES", "smiles"),
        )

        pubchem_identifier_tasks: dict[str, str] = {}
        for _, row in smiles_df.loc[smiles_df["isomeric_SMILES"].isna()].iterrows():
            metabolite_id = str(row["id_without_compartment"])
            collected_identifiers = self._collect_database_identifiers(
                metabolite_id=metabolite_id,
                model_data_index=model_data_index,
                metabolites_index=metabolites_index,
                recon3d_index=recon3d_index,
            )
            for chebi_identifier in collected_identifiers["chebi"]:
                smiles_value = chebi_mapping.get(chebi_identifier)
                if smiles_value is not None:
                    self._apply_smiles_to_row(
                        smiles_df=smiles_df,
                        metabolite_id=metabolite_id,
                        smiles_value=smiles_value,
                        source_name="chebi",
                        source_identifier=chebi_identifier,
                        source_query=None,
                    )
                    break
            if (
                smiles_df.loc[
                    smiles_df["id_without_compartment"] == metabolite_id,
                    "isomeric_SMILES",
                ]
                .notna()
                .any()
            ):
                continue
            for metanetx_identifier in collected_identifiers["metanetx"]:
                smiles_value = metanetx_mapping.get(metanetx_identifier)
                if smiles_value is not None:
                    self._apply_smiles_to_row(
                        smiles_df=smiles_df,
                        metabolite_id=metabolite_id,
                        smiles_value=smiles_value,
                        source_name="metanetx",
                        source_identifier=metanetx_identifier,
                        source_query=None,
                    )
                    break
            if (
                smiles_df.loc[
                    smiles_df["id_without_compartment"] == metabolite_id,
                    "isomeric_SMILES",
                ]
                .notna()
                .any()
            ):
                continue
            for pubchem_identifier in collected_identifiers["pubchem"]:
                pubchem_identifier_tasks.setdefault(pubchem_identifier, metabolite_id)

        pubchem_candidates_by_identifier = (
            self.pubchem_lookup_service.fetch_candidates_by_cid(
                list(pubchem_identifier_tasks.keys())
            )
        )
        for pubchem_identifier, metabolite_id in pubchem_identifier_tasks.items():
            if (
                smiles_df.loc[
                    smiles_df["id_without_compartment"] == metabolite_id,
                    "isomeric_SMILES",
                ]
                .notna()
                .any()
            ):
                continue
            selected_candidate = self._select_pubchem_candidate(
                candidates=pubchem_candidates_by_identifier.get(pubchem_identifier, []),
                metabolite_formula=_normalise_optional_string(
                    smiles_df.loc[
                        smiles_df["id_without_compartment"] == metabolite_id,
                        "formula",
                    ].iloc[0]
                ),
            )
            if selected_candidate is None:
                continue
            self._apply_pubchem_candidate(
                smiles_df=smiles_df,
                metabolite_id=metabolite_id,
                candidate=selected_candidate,
                source_name="pubchem_id",
                source_query=pubchem_identifier,
            )

    def _build_simple_lookup_mapping(
        self,
        dataframe: pd.DataFrame | None,
        *,
        identifier_column_candidates: Sequence[str],
        smiles_column_candidates: Sequence[str],
    ) -> dict[str, str]:
        """Generated: validation needed.

        Description:
            Build generic identifier-to-smiles mapping from local dataframe.

        Args:
            dataframe (pd.DataFrame | None): Local lookup table.
            identifier_column_candidates (Sequence[str]): Candidate identifier columns.
            smiles_column_candidates (Sequence[str]): Candidate smiles columns.

        Returns:
            dict[str, str]: Identifier to smiles mapping.
        """

        if dataframe is None or dataframe.empty:
            return {}
        identifier_column = next(
            (
                column_name
                for column_name in identifier_column_candidates
                if column_name in dataframe.columns
            ),
            None,
        )
        smiles_column = next(
            (
                column_name
                for column_name in smiles_column_candidates
                if column_name in dataframe.columns
            ),
            None,
        )
        if identifier_column is None or smiles_column is None:
            return {}
        mapping: dict[str, str] = {}
        for _, row in dataframe.iterrows():
            identifier = _normalise_optional_string(row.get(identifier_column))
            smiles_value = _normalise_optional_string(row.get(smiles_column))
            if identifier is None or smiles_value is None:
                continue
            mapping[identifier] = smiles_value
        return mapping

    def _collect_database_identifiers(
        self,
        *,
        metabolite_id: str,
        model_data_index: dict[str, dict[str, Any]],
        metabolites_index: dict[str, dict[str, Any]],
        recon3d_index: dict[str, dict[str, Any]],
    ) -> dict[str, list[str]]:
        """Generated: validation needed.

        Description:
            Gather database identifiers from model tables and Recon3D annotations.

        Args:
            metabolite_id (str): Target metabolite ID.
            model_data_index (dict[str, dict[str, Any]]): Indexed model metadata.
            metabolites_index (dict[str, dict[str, Any]]): Indexed metabolites table.
            recon3d_index (dict[str, dict[str, Any]]): Indexed Recon3D annotations.

        Returns:
            dict[str, list[str]]: Identifier groups for ChEBI, MetaNetX, and PubChem.
        """

        identifiers = {
            "chebi": [],
            "metanetx": [],
            "pubchem": [],
        }
        metabolites_row = metabolites_index.get(metabolite_id, {})
        model_data_row = model_data_index.get(metabolite_id, {})

        for key_name in ("metChEBIID",):
            identifiers["chebi"].extend(_split_identifier_cell(metabolites_row.get(key_name)))
        for key_name in ("metMetaNetXID", "metEHMNID"):
            identifiers["metanetx"].extend(
                _split_identifier_cell(metabolites_row.get(key_name))
            )
        for key_name in ("metPubChemID",):
            identifiers["pubchem"].extend(
                _split_identifier_cell(metabolites_row.get(key_name))
            )

        for key_name, identifier_group in _parse_miriam_identifiers(
            model_data_row.get("MIRIAM")
        ).items():
            if key_name == "chebi":
                identifiers["chebi"].extend(identifier_group)
            elif key_name in {"metanetx.chemical", "metEHMNID"}:
                identifiers["metanetx"].extend(identifier_group)
            elif key_name == "pubchem.compound":
                identifiers["pubchem"].extend(identifier_group)

        recon3d_identifier = _normalise_optional_string(metabolites_row.get("metRecon3DID"))
        if recon3d_identifier is not None:
            recon3d_annotation = recon3d_index.get(
                _normalise_metabolite_identifier(recon3d_identifier),
                {},
            )
            for key_name, annotation_value in recon3d_annotation.items():
                annotation_values = _split_identifier_cell(annotation_value)
                if key_name == "chebi":
                    identifiers["chebi"].extend(annotation_values)
                elif key_name in {"metanetx.chemical", "metEHMNID"}:
                    identifiers["metanetx"].extend(annotation_values)
                elif key_name == "pubchem.compound":
                    identifiers["pubchem"].extend(annotation_values)

        return {
            group_name: list(dict.fromkeys(identifier_values))
            for group_name, identifier_values in identifiers.items()
        }

    def _apply_pubchem_name_lookups(self, *, smiles_df: pd.DataFrame) -> None:
        """Generated: validation needed.

        Description:
            Resolve unresolved metabolites with direct PubChem name lookups.

        Args:
            smiles_df (pd.DataFrame): Working SMILES dataframe.
        """

        query_names = [
            str(row["name"])
            for _, row in smiles_df.loc[smiles_df["isomeric_SMILES"].isna()].iterrows()
        ]
        candidates_by_query = self.pubchem_lookup_service.fetch_candidates(query_names)
        for _, row in smiles_df.loc[smiles_df["isomeric_SMILES"].isna()].iterrows():
            selected_candidate = self._select_pubchem_candidate(
                candidates=candidates_by_query.get(str(row["name"]), []),
                metabolite_formula=_normalise_optional_string(row.get("formula")),
            )
            if selected_candidate is None:
                continue
            self._apply_pubchem_candidate(
                smiles_df=smiles_df,
                metabolite_id=str(row["id_without_compartment"]),
                candidate=selected_candidate,
                source_name="pubchem_name",
                source_query=str(row["name"]),
            )

    def _apply_synonym_pubchem_lookups(
        self,
        *,
        smiles_df: pd.DataFrame,
        metabolite_name_synonyms_df: pd.DataFrame | None,
    ) -> None:
        """Generated: validation needed.

        Description:
            Resolve remaining metabolites through synonym and transformed-name PubChem
            lookups.

        Args:
            smiles_df (pd.DataFrame): Working SMILES dataframe.
            metabolite_name_synonyms_df (pd.DataFrame | None): Optional synonyms table.
        """

        missing_rows = smiles_df.loc[smiles_df["isomeric_SMILES"].isna()].copy()
        if missing_rows.empty:
            return

        synonyms_by_name = self._build_synonyms_by_name(metabolite_name_synonyms_df)
        query_plan: dict[str, list[tuple[str, str, str | None]]] = defaultdict(list)
        for _, row in missing_rows.iterrows():
            metabolite_id = str(row["id_without_compartment"])
            metabolite_name = str(row["name"])
            for query_name, bound_form in self._build_alternative_query_terms(
                metabolite_name=metabolite_name,
                synonyms_by_name=synonyms_by_name,
            ):
                query_plan[query_name].append((metabolite_id, metabolite_name, bound_form))

        if not query_plan:
            return

        candidates_by_query = self.pubchem_lookup_service.fetch_candidates(list(query_plan))
        for query_name, targets in query_plan.items():
            candidates = candidates_by_query.get(query_name, [])
            if not candidates:
                continue
            for metabolite_id, metabolite_name, bound_form in targets:
                row_mask = smiles_df["id_without_compartment"] == metabolite_id
                if smiles_df.loc[row_mask, "isomeric_SMILES"].notna().any():
                    continue
                metabolite_formula = _normalise_optional_string(
                    smiles_df.loc[row_mask, "formula"].iloc[0]
                )
                selected_candidate = self._select_pubchem_candidate(
                    candidates=candidates,
                    metabolite_formula=metabolite_formula,
                )
                if selected_candidate is None:
                    continue
                if bound_form is None:
                    self._apply_pubchem_candidate(
                        smiles_df=smiles_df,
                        metabolite_id=metabolite_id,
                        candidate=selected_candidate,
                        source_name="pubchem_synonym",
                        source_query=query_name,
                    )
                    continue
                transformed_smiles = self._transform_bound_smiles(
                    smiles_value=(
                        selected_candidate.isomeric_smiles
                        or selected_candidate.canonical_smiles
                    ),
                    bound_form=bound_form,
                )
                if transformed_smiles is None:
                    continue
                self._apply_smiles_to_row(
                    smiles_df=smiles_df,
                    metabolite_id=metabolite_id,
                    smiles_value=transformed_smiles,
                    source_name=f"pubchem_synonym_{bound_form}",
                    source_identifier=selected_candidate.compound_id,
                    source_query=query_name,
                )

    def _build_synonyms_by_name(
        self,
        metabolite_name_synonyms_df: pd.DataFrame | None,
    ) -> dict[str, list[str]]:
        """Generated: validation needed.

        Description:
            Convert optional synonym table into metabolite-name lookup dictionary.

        Args:
            metabolite_name_synonyms_df (pd.DataFrame | None): Synonym dataframe.

        Returns:
            dict[str, list[str]]: Metabolite name to synonym list mapping.
        """

        if metabolite_name_synonyms_df is None or metabolite_name_synonyms_df.empty:
            return {}
        renamed_df = metabolite_name_synonyms_df.copy()
        lowered_columns = {
            str(column).strip().lower(): column for column in renamed_df.columns
        }
        name_column = (
            lowered_columns.get("# met name in the model")
            or lowered_columns.get("metabolite_name")
            or lowered_columns.get("name")
        )
        synonym_column = lowered_columns.get("synonym")
        if name_column is None or synonym_column is None:
            return {}
        synonyms_by_name: dict[str, list[str]] = defaultdict(list)
        for _, row in renamed_df.iterrows():
            metabolite_name = _normalise_optional_string(row.get(name_column))
            synonym = _normalise_optional_string(row.get(synonym_column))
            if metabolite_name is None or synonym is None:
                continue
            synonyms_by_name[metabolite_name].append(synonym)
        return dict(synonyms_by_name)

    def _build_alternative_query_terms(
        self,
        *,
        metabolite_name: str,
        synonyms_by_name: dict[str, list[str]],
    ) -> list[tuple[str, str | None]]:
        """Generated: validation needed.

        Description:
            Build ordered alternative PubChem queries for one metabolite name.

        Args:
            metabolite_name (str): Original metabolite name.
            synonyms_by_name (dict[str, list[str]]): Name-to-synonyms mapping.

        Returns:
            list[tuple[str, str | None]]: Ordered `(query_name, bound_form)` pairs.
        """

        query_terms: list[tuple[str, str | None]] = []
        seen_query_terms: set[tuple[str, str | None]] = set()

        def add_query(query_name: str | None, bound_form: str | None = None) -> None:
            normalised_query = _normalise_optional_string(query_name)
            if normalised_query is None:
                return
            query_entry = (normalised_query, bound_form)
            if query_entry in seen_query_terms or normalised_query == metabolite_name:
                return
            query_terms.append(query_entry)
            seen_query_terms.add(query_entry)

        for synonym in synonyms_by_name.get(metabolite_name, []):
            add_query(synonym)

        lowered_name = metabolite_name.lower()
        for suffix, replacements in _SUFFIX_REPLACEMENTS.items():
            if not lowered_name.endswith(suffix.lower()):
                continue
            start_index = len(metabolite_name) - len(suffix)
            prefix = metabolite_name[:start_index]
            for replacement in replacements:
                add_query(f"{prefix}{replacement}")

        if _OYL_PATTERN.search(metabolite_name):
            bound_form = self._infer_bound_form(metabolite_name)
            stripped_name = _OYL_PATTERN.sub("", metabolite_name)
            add_query(f"{stripped_name}oic acid", bound_form)
            add_query(f"{stripped_name}ic acid", bound_form)

        return query_terms

    def _apply_coa_to_acp_fallback(self, smiles_df: pd.DataFrame) -> None:
        """Generated: validation needed.

        Description:
            Convert resolved CoA metabolite SMILES into ACP forms for unresolved ACP
            metabolites.

        Args:
            smiles_df (pd.DataFrame): Working SMILES dataframe.
        """

        missing_rows = smiles_df.loc[smiles_df["isomeric_SMILES"].isna()].copy()
        if missing_rows.empty:
            return
        resolved_by_name = {
            str(row["name"]): _normalise_optional_string(row.get("isomeric_SMILES"))
            for _, row in smiles_df.loc[smiles_df["isomeric_SMILES"].notna()].iterrows()
        }
        for _, row in missing_rows.iterrows():
            metabolite_name = str(row["name"])
            if not (metabolite_name.endswith("ACP") or metabolite_name.endswith("[ACP]")):
                continue
            coa_name = (
                metabolite_name.replace("[ACP]", "CoA")
                if metabolite_name.endswith("[ACP]")
                else metabolite_name.replace("ACP", "CoA")
            )
            coa_smiles = resolved_by_name.get(coa_name)
            if coa_smiles is None:
                continue
            acp_smiles = _ACP_FROM_COA_PATTERN.sub(_ACP_FRAGMENT, coa_smiles)
            if acp_smiles == coa_smiles:
                continue
            self._apply_smiles_to_row(
                smiles_df=smiles_df,
                metabolite_id=str(row["id_without_compartment"]),
                smiles_value=acp_smiles,
                source_name="coa_to_acp_fallback",
                source_identifier=coa_name,
                source_query=coa_name,
            )

    def _select_pubchem_candidate(
        self,
        *,
        candidates: Sequence[PubChemCandidate],
        metabolite_formula: str | None,
    ) -> PubChemCandidate | None:
        """Generated: validation needed.

        Description:
            Select best PubChem candidate using formula matching and protonation heuristics.

        Args:
            candidates (Sequence[PubChemCandidate]): Candidate compounds.
            metabolite_formula (str | None): Target metabolite formula.

        Returns:
            PubChemCandidate | None: Selected candidate, or None when nothing suitable exists.
        """

        filtered_candidates = [
            candidate
            for candidate in candidates
            if candidate.isomeric_smiles or candidate.canonical_smiles or candidate.inchi
        ]
        if not filtered_candidates:
            return None
        if len(filtered_candidates) == 1:
            return filtered_candidates[0]
        if metabolite_formula is not None:
            exact_matches = [
                candidate
                for candidate in filtered_candidates
                if _formula_matches(
                    candidate_formula=candidate.molecular_formula,
                    reference_formula=metabolite_formula,
                )
            ]
            if len(exact_matches) == 1:
                return exact_matches[0]
            if len(exact_matches) > 1:
                filtered_candidates = exact_matches
        return (
            self._choose_protonation_candidate(filtered_candidates) or filtered_candidates[0]
        )

    def _choose_protonation_candidate(
        self,
        candidates: Sequence[PubChemCandidate],
    ) -> PubChemCandidate | None:
        """Generated: validation needed.

        Description:
            Select candidate with highest or lowest protonation among comparable formulas.

        Args:
            candidates (Sequence[PubChemCandidate]): Candidate compounds.

        Returns:
            PubChemCandidate | None: Selected candidate, or None when formulas are
            unavailable.
        """

        comparable_candidates: list[tuple[int, PubChemCandidate]] = []
        for candidate in candidates:
            if candidate.molecular_formula is None:
                continue
            match = _PROTONATION_PATTERN.match(candidate.molecular_formula)
            if match is None:
                continue
            hydrogen_count = int(match.group("hydrogen") or 0)
            comparable_candidates.append((hydrogen_count, candidate))
        if not comparable_candidates:
            return None
        sorted_candidates = sorted(
            comparable_candidates,
            key=lambda item: item[0],
            reverse=self.use_most_protonated_smiles,
        )
        return sorted_candidates[0][1]

    def _apply_pubchem_candidate(
        self,
        *,
        smiles_df: pd.DataFrame,
        metabolite_id: str,
        candidate: PubChemCandidate,
        source_name: str,
        source_query: str,
    ) -> None:
        """Generated: validation needed.

        Description:
            Write selected PubChem candidate into dataframe.

        Args:
            smiles_df (pd.DataFrame): Working SMILES dataframe.
            metabolite_id (str): Target metabolite ID.
            candidate (PubChemCandidate): Selected PubChem candidate.
            source_name (str): Source label.
            source_query (str): Query used to obtain candidate.
        """

        smiles_value = candidate.isomeric_smiles or candidate.canonical_smiles
        if smiles_value is None and candidate.inchi is not None:
            self._apply_inchi_to_row(
                smiles_df=smiles_df,
                metabolite_id=metabolite_id,
                inchi_value=candidate.inchi,
                source_name=source_name,
                source_identifier=candidate.compound_id or candidate.query,
            )
            row_mask = smiles_df["id_without_compartment"] == metabolite_id
            smiles_df.loc[row_mask, "source_query"] = source_query
            return
        if smiles_value is None:
            return
        self._apply_smiles_to_row(
            smiles_df=smiles_df,
            metabolite_id=metabolite_id,
            smiles_value=smiles_value,
            source_name=source_name,
            source_identifier=candidate.compound_id,
            source_query=source_query,
        )

    def _transform_bound_smiles(
        self, *, smiles_value: str | None, bound_form: str
    ) -> str | None:
        """Generated: validation needed.

        Description:
            Transform acid-form SMILES into CoA- or ACP-bound variant.

        Args:
            smiles_value (str | None): Acid-form SMILES string.
            bound_form (str): Requested bound-form mode.

        Returns:
            str | None: Transformed bound-form SMILES, or None when conversion fails.
        """

        normalised_smiles = _normalise_optional_string(smiles_value)
        if normalised_smiles is None:
            return None
        replacement = _COA_FRAGMENT if bound_form == "coa" else _ACP_FRAGMENT
        transformed_smiles = re.sub(r"(\(=O\)O)", f"(=O){replacement}", normalised_smiles)
        if transformed_smiles == normalised_smiles:
            return None
        return transformed_smiles

    @staticmethod
    def _infer_bound_form(metabolite_name: str) -> str:
        """Generated: validation needed.

        Description:
            Infer whether transformed lookup should recreate CoA or ACP bound form.

        Args:
            metabolite_name (str): Original metabolite name.

        Returns:
            str: Bound-form identifier.
        """

        if metabolite_name.endswith("ACP") or metabolite_name.endswith("[ACP]"):
            return "acp"
        return "coa"

    def _finalise_smiles_dataframe(self, smiles_df: pd.DataFrame) -> pd.DataFrame:
        """Generated: validation needed.

        Description:
            Add compatibility columns and final diagnostics columns to SMILES dataframe.

        Args:
            smiles_df (pd.DataFrame): Working SMILES dataframe.

        Returns:
            pd.DataFrame: Final sorted SMILES dataframe.
        """

        final_smiles_df = smiles_df.copy()
        if "InChIKey" not in final_smiles_df.columns:
            final_smiles_df["InChIKey"] = None
        final_smiles_df["isomeric SMILES"] = final_smiles_df["isomeric_SMILES"]
        final_smiles_df["canonical SMILES"] = final_smiles_df["canonical_SMILES"]
        final_smiles_df["missing_smiles"] = final_smiles_df["isomeric_SMILES"].isna() | (
            final_smiles_df["isomeric_SMILES"] == ""
        )
        final_smiles_df["smiles_longer_than_218"] = final_smiles_df["isomeric_SMILES"].map(
            lambda smiles_value: (
                len(str(smiles_value)) > self.smiles_length_limit
                if _normalise_optional_string(smiles_value) is not None
                else False
            )
        )
        for column_name in SMILES_OUTPUT_COLUMNS:
            if column_name not in final_smiles_df.columns:
                final_smiles_df[column_name] = None
        return (
            final_smiles_df[SMILES_OUTPUT_COLUMNS]
            .sort_values(by=["id_without_compartment"])
            .reset_index(drop=True)
        )

    @staticmethod
    def _count_missing(smiles_df: pd.DataFrame) -> int:
        """Generated: validation needed.

        Description:
            Count currently unresolved metabolites in working dataframe.

        Args:
            smiles_df (pd.DataFrame): Working SMILES dataframe.

        Returns:
            int: Number of unresolved rows.
        """

        return int(smiles_df["isomeric_SMILES"].isna().sum())


def _split_identifier_cell(value: Any) -> list[str]:
    """Generated: validation needed.

    Description:
        Split identifier cell that may contain lists, semicolon-delimited values, or strings.

    Args:
        value (Any): Cell value to split.

    Returns:
        list[str]: Parsed identifiers.
    """

    if value is None:
        return []
    if isinstance(value, list):
        parsed_values = [_normalise_optional_string(entry) for entry in value]
        return [entry for entry in parsed_values if entry is not None]
    normalised_value = _normalise_optional_string(value)
    if normalised_value is None:
        return []
    sanitised_value = normalised_value.replace("[", "").replace("]", "")
    split_values = re.split(r"[;,]", sanitised_value)
    return [
        entry
        for entry in (_normalise_optional_string(item) for item in split_values)
        if entry
    ]


def _parse_miriam_identifiers(value: Any) -> dict[str, list[str]]:
    """Generated: validation needed.

    Description:
        Parse MIRIAM annotation string into grouped identifier mapping.

    Args:
        value (Any): Raw MIRIAM cell value.

    Returns:
        dict[str, list[str]]: Grouped identifiers keyed by namespace.
    """

    normalised_value = _normalise_optional_string(value)
    if normalised_value is None:
        return {}
    grouped_identifiers: dict[str, list[str]] = defaultdict(list)
    for entry in normalised_value.split(";"):
        namespace, _, identifier = entry.partition("/")
        parsed_namespace = _normalise_optional_string(namespace)
        parsed_identifier = _normalise_optional_string(identifier)
        if parsed_namespace is None or parsed_identifier is None:
            continue
        grouped_identifiers[parsed_namespace].append(parsed_identifier)
    return dict(grouped_identifiers)


def _formula_matches(candidate_formula: str | None, reference_formula: str) -> bool:
    """Generated: validation needed.

    Description:
        Determine whether candidate formula matches reference formula after light
        normalisation.

    Args:
        candidate_formula (str | None): Candidate formula from external source.
        reference_formula (str): Reference metabolite formula.

    Returns:
        bool: True when formulas are compatible.
    """

    if candidate_formula is None:
        return False
    if candidate_formula == reference_formula:
        return True
    stripped_candidate = re.sub(r"-\d+$", "", candidate_formula)
    if stripped_candidate == reference_formula:
        return True
    candidate_match = _PROTONATION_PATTERN.match(candidate_formula)
    reference_match = _PROTONATION_PATTERN.match(reference_formula)
    if candidate_match is None or reference_match is None:
        return False
    return candidate_match.group("base") == reference_match.group(
        "base"
    ) and candidate_match.group("suffix") == reference_match.group("suffix")
