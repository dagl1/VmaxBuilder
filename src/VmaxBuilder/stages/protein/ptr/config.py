from dataclasses import dataclass


@dataclass(slots=True)
class PTRInputConfig:
    """Generated: validation needed.

    Description:
        PTR input option group used by expression+PTR protein abundance flow.

    Args:
        id_type (str): Identifier provider for PTR features.
        level (str): Gene or transcript level granularity.
        pretransformed_type (str): Log-scale used in raw PTR input before
            linear conversion. One of ``linear``, ``log10``, ``log2``, ``ln``.
        partial_missing_use_weighted (bool): Whether within-sample imputation
            should apply per-sample weighting. ``True`` keeps weighted column
            scaling; ``False`` uses unweighted row-statistic imputation.
        partial_missing_weighted_statistic (str): Column statistic used for
            weighted scaling during within-sample imputation. One of
            ``median``, ``mean``, ``mode``, ``max``, ``min``.
        partial_missing_imputation_statistic (str): Row statistic used for
            within-sample imputation of observed-but-missing PTR values.
            One of ``median``, ``mean``, ``mode``, ``max``, ``min``.
        unobserved_gene_imputation_strategy (str): Strategy used to fill genes
            present in expression but absent from PTR. One of
            ``sample_after_imputation``, ``sample_before_imputation``.
        unobserved_gene_imputation_statistic (str): Per-sample statistic used
            when imputing unobserved genes. One of ``median``, ``mean``,
            ``max``, ``min``.
        use_special_groups_for_unobserved_imputation (bool): Whether to impute
            configured special gene groups independently.
        special_gene_groups (dict[str, list[str]] | None): Optional custom
            grouping entries to impute independently. Values may contain gene
            IDs or reaction IDs; ``transport_reactions`` may be given with an
            empty list to auto-resolve transport-associated genes from model.
        impute_from_metabolic_genes_only (bool): Restrict PTR prior to
            imputation to genes found in the metabolic model.
    """

    PTR_protein_id_type: str = "ensembl"
    PTR_level: str = "gene"
    PTR_pretransformed_type: str = "log10"
    partial_missing_use_weighted: bool = True
    partial_missing_weighted_statistic: str = "median"
    partial_missing_imputation_statistic: str = "median"
    unobserved_gene_imputation_strategy: str = "sample_after_imputation"
    unobserved_gene_imputation_statistic: str = "median"
    use_special_groups_for_unobserved_imputation: bool = False
    PTR_special_gene_groups: dict[str, list[str]] | None = None
    impute_from_metabolic_genes_only: bool = True
    expression_sample_type_map: dict[str | int, str] | str | None = None
