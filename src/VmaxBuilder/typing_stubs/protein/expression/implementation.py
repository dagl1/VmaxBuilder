from typing import Protocol


class ExpressionConfigProtocol(Protocol):
    expression_gene_id_type: str | None = "ensembl"
    expression_level: str = "gene"
    sample_type_map: dict[str, str] | str | None = None
    transformation_state: str = "linear"
    data_type: str = "TPM"
    thresholding: bool | str = False
    protein_coding_aggregation_policy: str = "sum"
    transcript_aggregation_policy: str = "sum"
    minimum_expression_threshold: float = 0.001
    minimum_expression_threshold_policy: str = "set_to_missing"  # "raise_to_threshold
    missing_gene_policy: str = "GPRless"
