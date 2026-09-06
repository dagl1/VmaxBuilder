from dataclasses import dataclass


@dataclass
class MainSubstrateConfig:
    prediction_value_column: str = "median"
    mark_passive_transport_reactions_as_missing: bool = True
    prediction_transformation_state: str = "log10"  # options: ["log10", "none"]
    main_substrate_selection_statistic: str = "max"
    missing_prediction_strategy: str = "all"  # options: ["all", "per_compartment"]
    missing_prediction_statistic: str = "median"  # options: ["mean", "median"]
