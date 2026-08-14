from typing import Protocol


class MainSubstrateConfigProtocol(Protocol):
    main_substrate_selection_statistic: str = "max"
    missing_prediction_strategy: str = "all"  # options: ["all", "per_compartment"]
    missing_prediction_statistic: str = "median"  # options: ["mean", "median"]
