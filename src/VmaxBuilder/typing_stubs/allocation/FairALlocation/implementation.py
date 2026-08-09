from typing import Protocol


class FairAllocationConfigProtocol(Protocol):
    trim_minimum_proteins_in_IFP: int = 7  # trimming is only done when at any step there
