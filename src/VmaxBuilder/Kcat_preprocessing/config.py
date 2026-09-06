from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from VmaxBuilder.base.classes import ImplementationConfig
from VmaxBuilder.Kcat_preprocessing.smiles_retrieval import DEFAULT_SMILES_LENGTH_LIMIT


class TranscriptSmilesGetterConfigProtocol(Protocol):
    """Generated: validation needed.

    Description:
        Structural config contract used by TranscriptSMILESGetter implementation.

    Attributes:
        use_most_protonated_smiles (bool): Selects multi-hit PubChem protonation
            preference logic.
        smiles_length_limit (int): Length threshold used for SMILES diagnostics.
        retrieve_transcript_metadata (bool): Enables gene->transcript retrieval when
            transcript dataframe is not supplied.
        retrieve_alternative_transcripts (bool): Keeps alternative transcript rows in
            addition to canonical rows.
        include_cdna_sequence (bool): Retrieves cDNA sequence metadata alongside AA
            sequence metadata.
        enrich_existing_transcript_df_with_sequences (bool): Enriches provided
            transcript dataframe rows with sequence metadata.
    """

    use_most_protonated_smiles: bool
    smiles_length_limit: int
    retrieve_transcript_metadata: bool
    retrieve_alternative_transcripts: bool
    include_cdna_sequence: bool
    enrich_existing_transcript_df_with_sequences: bool


@dataclass(slots=True)
class TranscriptSmilesGetterConfig(ImplementationConfig):
    """Generated: validation needed.

    Description:
        Runtime options controlling model-stage SMILES and transcript retrieval behaviour.

    Args:
        use_most_protonated_smiles (bool): Whether multi-hit PubChem matches prefer
            most protonated compatible formula variant.
        smiles_length_limit (int): Length threshold used for UniKP diagnostics.
        retrieve_transcript_metadata (bool): Whether transcript metadata should be
            looked up when transcript_df is absent from scaffold.
        retrieve_alternative_transcripts (bool): Whether to retain alternative
            transcript rows in addition to canonical rows.
        include_cdna_sequence (bool): Whether to fetch cDNA sequence metadata during
            transcript retrieval.
        enrich_existing_transcript_df_with_sequences (bool): Whether provided
            transcript_df should be enriched with AA/cDNA sequence metadata.
    """

    use_most_protonated_smiles: bool = True
    smiles_length_limit: int = DEFAULT_SMILES_LENGTH_LIMIT
    retrieve_transcript_metadata: bool = True
    retrieve_alternative_transcripts: bool = False
    include_cdna_sequence: bool = False
    enrich_existing_transcript_df_with_sequences: bool = True


