from dataclasses import dataclass


@dataclass
class ReactionResolvingConfig:
    trim_genes_remain_part_for_Kcat: bool = True
    save_ifp_sample_abundance_artifact: bool = True
    include_gene_details_in_ifp_sample_abundance_artifact: bool = False
