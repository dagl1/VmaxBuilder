from dataclasses import dataclass


@dataclass
class ExpressionConfig:
    id_type: str | None = "ensembl"
    level: str = "gene"
    sample_type_map: dict[str, str] | str | None = None
    transformation_state: str = "log"
    data_type: str = "TPM"
    thresholding: bool | str = False
    protein_coding_aggregation_policy: str = "sum"
    transcript_aggregation_policy: str = "sum"
