"""Generated: validation needed.

Description:
    Allocation-stage placeholder implementation until strategy migration is completed.
"""

from __future__ import annotations

from VmaxBuilder.config.dataclasses import APIConfig
from VmaxBuilder.core.protocols import Scaffold
from VmaxBuilder.config.registry import register_implementation, AllocationImplementation


@register_implementation(AllocationImplementation, "default_placeholder")
class DefaultAllocationStageImplementation:
    """Generated: validation needed.

    Description:
        Record placeholder metadata for allocation stage during staged refactor.

    Modifies:
        scaffold["metadata"] payload.
    """

    def run(self, scaffold: Scaffold, config: APIConfig) -> Scaffold:
        """Generated: validation needed.

        Description:
            Append placeholder metadata for allocation stage.

        Args:
            scaffold (Scaffold): Shared pipeline scaffold.
            config (APIConfig): Root API configuration.

        Returns:
            Scaffold: Updated scaffold.

        Modifies:
            scaffold["metadata"].
        """
        # ensure we have the IFP mapping from the GPR stage
        # ensure we have protein abundance data from the protein stage
        # implement gene trimming
        IFP_mapping = scaffold.get("IFP_mapping")

        metadata_payload = scaffold.setdefault("metadata", {})
        metadata_payload["allocation_stage"] = {
            "status": "placeholder_not_implemented",
        }
        return scaffold
