from dataclasses import dataclass
from typing import Protocol

from VmaxBuilder.Kcat_preprocessing.smiles_retrieval import (
    DEFAULT_SMILES_LENGTH_LIMIT,
)


@dataclass(slots=True)
class TranscriptSmilesGetterConfig:
    """Generated: validation needed.

    Description:
        Runtime options controlling model-stage SMILES retrieval behaviour.

    Args:
        use_most_protonated_smiles (bool): Whether multi-hit PubChem matches prefer
            most protonated compatible formula variant.
        smiles_length_limit (int): Length threshold used for UniKP diagnostics.
        retrieve_transcript_metadata (bool): Whether missing transcript metadata should
            be retrieved automatically from identifier translation providers.
        retrieve_alternative_transcripts (bool): Whether transcript lookup should retain
            alternative transcript rows in addition to canonical rows.
    """

    use_most_protonated_smiles: bool = True
    smiles_length_limit: int = DEFAULT_SMILES_LENGTH_LIMIT
    retrieve_transcript_metadata: bool = True
    retrieve_alternative_transcripts: bool = False


class TranscriptSmilesGetterConfigProtocol(Protocol):
    """Protocol for TranscriptSmilesGetterConfig dataclass."""

    use_most_protonated_smiles: bool
    smiles_length_limit: int
    retrieve_transcript_metadata: bool
    retrieve_alternative_transcripts: bool
