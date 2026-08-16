from dataclasses import dataclass


@dataclass
class ReactionResolvingConfig:
    trim_genes_remain_part_for_Kcat: bool = True
