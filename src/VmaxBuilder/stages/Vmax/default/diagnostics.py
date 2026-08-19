from typing import Any

import pandas as pd

from VmaxBuilder.base.classes import BaseImplementationDiagnostics
from VmaxBuilder.base.configs import FullConfig, Scaffold

# todo:
# we want to be able to do the following plots;
# so we need to generate this data:
##### gene-substrate predictions
##### main-substrate predictions
##### IFP-dominant kcat prediction
##### IFP-allocation
##### reaction-summed allocation
##### reaction-summed vmax
##### reaction contribution per IFP (for both kcat and allocation)

# todo:
# calculate the correlation between the correlations of Kcat and abundance to Vmax
# do the same for abundance contribution vs vmax contribution to total vmax
# plot how the kcat predictions look in IFPs that make up the majority of a total Vmax
# For 3 way correlation, we  can use VIF
#

# todo:
# categorise reactions into buckets depending on how their IFP contributions differ.
# Then per bucket, show the average contribution of the nth highest contributors

# todo:
# plot at each level what happens if we would substitute abundance or kcat with
# a static value


class VmaxDiagnostics(BaseImplementationDiagnostics):
    """Generated: validation needed.

    Description:
        Model-stage diagnostics for preparing reaction alluvial data.
    """

    DIAGNOSTICS_NAME = "Vmax"

    def __init__(self, full_config: FullConfig):
        """Generated: validation needed.

        Description:
            Initialise model diagnostics state and logger.

        Args:
            full_config (FullConfig): Full pipeline configuration.

        Modifies:
            Internal diagnostics cache and base logger state.
        """
        super().__init__(full_config)

    def before_run(self, scaffold: Scaffold) -> dict[str, dict[str, Any]]:
        return {"outputs": {}, "diagnostics": {}, "metadata": {}, "artifacts": {}}

    def after_run(
        self,
        scaffold_objects: dict[str, dict[str, Any]],
        scaffold: Scaffold,
    ) -> dict[str, dict[str, Any]]:
        # add in flux transformation
        # overlaid histograms
        # overlaid cdfs for different samples
        # trimming vs non_trimming

        diagnostics = {"Vmax": []}
        new_scaffold_objects = {
            "outputs": {},
            "diagnostics": diagnostics,
            "metadata": {},
            "artifacts": {},
        }
        return new_scaffold_objects
