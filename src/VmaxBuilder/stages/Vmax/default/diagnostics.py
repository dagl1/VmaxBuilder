from __future__ import annotations

from typing import Any, cast

import pandas as pd

from VmaxBuilder.base.classes import BaseImplementationDiagnostics, DiagnosticOutputSpec
from VmaxBuilder.base.configs import FullConfig, Scaffold


class VmaxDiagnostics(BaseImplementationDiagnostics):
    """Generated: validation needed.

    Description:
        Provide lightweight single-run Vmax diagnostics payload.
    """

    DIAGNOSTICS_NAME = "Vmax"

    def __init__(self, full_config: FullConfig):
        """Generated: validation needed.

        Description:
            Initialise Vmax diagnostics state and logger.

        Args:
            full_config (FullConfig): Full pipeline configuration.

        Modifies:
            Base diagnostics logger state.
        """
        super().__init__(full_config)

    def before_run(self, scaffold: Scaffold) -> dict[str, dict[str, Any]]:
        """Generated: validation needed.

        Description:
            Return empty diagnostics payload for before-run hook.

        Args:
            scaffold (Scaffold): Shared scaffold payload.

        Returns:
            dict[str, dict[str, Any]]: Empty before-run diagnostics payload.
        """
        return {"outputs": {}, "diagnostics": {}, "metadata": {}, "artifacts": {}}

    def after_run(
        self,
        scaffold_objects: dict[str, dict[str, Any]],
        scaffold: Scaffold,
    ) -> dict[str, dict[str, Any]]:
        """Generated: validation needed.

        Description:
            Build Vmax diagnostics payload for single-run reaction-capacity outputs.

        Args:
            scaffold_objects (dict[str, dict[str, Any]]): Stage output payload.
            scaffold (Scaffold): Shared scaffold payload.

        Returns:
            dict[str, dict[str, Any]]: Diagnostics payload.
        """
        trimmed_reaction_capacity_df = cast(
            pd.DataFrame | None,
            scaffold.get_scaffold_value("non_imputed_reaction_capacity_df"),
        )

        if trimmed_reaction_capacity_df is None:
            self.logger.warning(
                "Skipping Vmax diagnostics: 'non_imputed_reaction_capacity_df' missing."
            )
            return {
                "outputs": {},
                "diagnostics": {"Vmax": []},
                "metadata": {},
                "artifacts": {},
            }

        diagnostics_output: list[DiagnosticOutputSpec] = []

        return {
            "outputs": {},
            "diagnostics": {"Vmax": diagnostics_output},
            "metadata": {},
            "artifacts": {},
        }
