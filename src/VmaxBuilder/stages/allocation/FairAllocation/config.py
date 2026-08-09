from dataclasses import dataclass


@dataclass
class FairAllocationConfig:
    trim_minimum_proteins_in_IFP: int = 7  # trimming is only done when at any step there
    # are at least this many proteins in the IFP. As trimming iteratively removes lowest
    # expressed proteins, this prevents the IFP from being trimmed down to a
    # very small number of proteins.
