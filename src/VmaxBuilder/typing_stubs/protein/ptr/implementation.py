from typing import Protocol


class PTRInputConfigProtocol(Protocol):
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
