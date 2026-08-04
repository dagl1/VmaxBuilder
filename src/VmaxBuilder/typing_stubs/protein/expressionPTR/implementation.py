from typing import Protocol


class ExpressionPTRConfigProtocol(Protocol):
    expression_gene_id_type: str | None = "ensembl"
    expression_level: str = "gene"
    sample_type_map: dict[str, str] | str | None = None
    transformation_state: str = "log"
    data_type: str = "TPM"
    thresholding: bool | str = False
    protein_coding_aggregation_policy: str = "sum"
    transcript_aggregation_policy: str = "sum"
    minimum_expression_threshold: float = 0.001
    minimum_expression_threshold_policy: str = "set_to_missing"  # "raise_to_threshold
    missing_gene_policy: str = "GPRless"

    PTR_protein_id_type: str = "ensembl"
    PTR_level: str = "gene"
    PTR_pretransformed_type: str = "linear"
    partial_missing_use_weighted: bool = True
    partial_missing_weighted_statistic: str = "median"
    partial_missing_imputation_statistic: str = "median"
    unobserved_gene_imputation_strategy: str = "sample_after_imputation"
    unobserved_gene_imputation_statistic: str = "median"
    use_special_groups_for_unobserved_imputation: bool = False
    PTR_special_gene_groups: dict[str, list[str]] | None = None
    impute_from_metabolic_genes_only: bool = True
    expression_sample_type_map: dict[int | str, str] | str | None = None
