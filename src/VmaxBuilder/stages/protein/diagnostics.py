from __future__ import annotations

from typing import Any, cast

import pandas as pd
import plotly.graph_objects as go
from cobra import Model

from VmaxBuilder.base.classes import BaseImplementationDiagnostics, DiagnosticOutputSpec
from VmaxBuilder.base.configs import FullConfig, Scaffold
from VmaxBuilder.utils.plotting.config import PlotConfig


class ProteinSummaryDiagnostics(BaseImplementationDiagnostics):
    """Generated: validation needed.

    Description:
        Produce protein-stage diagnostics for reaction characterization and
        gene-to-reaction mapping structure after missing-gene processing.
    """

    DIAGNOSTICS_NAME = "protein_summary"

    def __init__(self, full_config: FullConfig):
        """Generated: validation needed.

        Description:
            Initialise protein summary diagnostics.

        Args:
            full_config (FullConfig): Full pipeline configuration.
        """
        super().__init__(full_config)

    def before_run(self, scaffold: Scaffold) -> dict[str, dict[str, Any]]:
        """Generated: validation needed.

        Description:
            Return empty before-run diagnostics payload.

        Args:
            scaffold (Scaffold): Shared scaffold payload.

        Returns:
            dict[str, dict[str, Any]]: Empty payload.
        """
        return {"outputs": {}, "diagnostics": {}, "metadata": {}, "artifacts": {}}

    def after_run(
        self,
        scaffold_objects: dict[str, dict[str, Any]],
        scaffold: Scaffold,
    ) -> dict[str, dict[str, Any]]:
        """Generated: validation needed.

        Description:
            Build protein-stage summary diagnostics and plots from adjusted model.

        Args:
            scaffold_objects (dict[str, dict[str, Any]]): Stage output payload.
            scaffold (Scaffold): Shared scaffold payload.

        Returns:
            dict[str, dict[str, Any]]: Diagnostics payload.
        """
        adjusted_model = cast(
            Model | None, scaffold.get_scaffold_value("adjusted_irreversible_cobra_model")
        )
        adjusted_reaction_to_ifp_mapping = cast(
            dict[str, Any] | None,
            scaffold.get_scaffold_value("adjusted_reaction_to_IFP_mapping"),
        )

        if adjusted_model is None or adjusted_reaction_to_ifp_mapping is None:
            self.logger.warning(
                "Skipping protein summary diagnostics: "
                "required adjusted scaffold values missing."
            )
            return {
                "outputs": {},
                "diagnostics": {"protein_summary": []},
                "metadata": {},
                "artifacts": {},
            }

        reaction_summary = self._create_reaction_summary(adjusted_model)
        gene_reaction_degree_df = self._build_gene_reaction_degree_df(
            adjusted_reaction_to_ifp_mapping
        )

        plot_config = PlotConfig(width=1100, height=760)
        reaction_type_plot = self._create_reaction_type_plot(
            reaction_summary,
            plot_config=plot_config,
        )
        gene_reaction_degree_plot = self._create_gene_reaction_degree_plot(
            gene_reaction_degree_df,
            plot_config=plot_config,
        )

        return {
            "outputs": {},
            "diagnostics": {
                "protein_summary": [
                    DiagnosticOutputSpec(
                        data=reaction_summary,
                        save_file_name="reaction_characterization_summary",
                        extensions=[".json"],
                        data_type=dict,
                    ),
                    DiagnosticOutputSpec(
                        data=gene_reaction_degree_df,
                        save_file_name="gene_to_reaction_degree_summary",
                        extensions=[".csv", ".xlsx"],
                        data_type=pd.DataFrame,
                    ),
                    DiagnosticOutputSpec(
                        data=reaction_type_plot,
                        save_file_name="reaction_type_distribution",
                        extensions=[".svg", ".html"],
                        data_type=go.Figure,
                    ),
                    DiagnosticOutputSpec(
                        data=gene_reaction_degree_plot,
                        save_file_name="gene_reaction_degree_distribution",
                        extensions=[".svg", ".html"],
                        data_type=go.Figure,
                    ),
                ]
            },
            "metadata": {},
            "artifacts": {},
        }

    def _create_reaction_summary(self, model: Model) -> dict[str, Any]:
        """Generated: validation needed.

        Description:
            Summarise reaction classes after missing-gene processing.

        Args:
            model (Model): Adjusted model.

        Returns:
            dict[str, Any]: Reaction summary data.
        """
        reactions = list(model.reactions)
        gprless_reaction_ids = [reaction.id for reaction in reactions if not reaction.genes]
        reversible_count = sum(1 for reaction in reactions if reaction.reversibility)
        irreversible_count = len(reactions) - reversible_count

        return {
            "total_reactions": len(reactions),
            "gprless_reaction_count": len(gprless_reaction_ids),
            "gprless_reactions": gprless_reaction_ids,
            "reversible_reaction_count": reversible_count,
            "irreversible_reaction_count": irreversible_count,
            "exchange_reaction_count": sum(1 for reaction in reactions if reaction.boundary),
        }

    def _build_gene_reaction_degree_df(
        self,
        reaction_to_ifp_mapping: dict[str, Any],
    ) -> pd.DataFrame:
        """Generated: validation needed.

        Description:
            Build gene-to-reaction degree table from reaction IFP mapping.

        Args:
            reaction_to_ifp_mapping (dict[str, Any]): Reaction to IFP payload.

        Returns:
            pd.DataFrame: Gene reaction degree table.
        """
        gene_to_reactions: dict[str, set[str]] = {}
        for reaction_id, mapping_entry in reaction_to_ifp_mapping.items():
            ifps = mapping_entry.get("IFP_objects", [])
            for ifp_data in ifps:
                genes_in_ifp = ifp_data.get("genes_in_IFP", [])
                for gene_id in genes_in_ifp:
                    gene_to_reactions.setdefault(str(gene_id), set()).add(str(reaction_id))

        degree_df = pd.DataFrame(
            {
                "gene_id": list(gene_to_reactions.keys()),
                "reaction_count": [
                    len(reactions) for reactions in gene_to_reactions.values()
                ],
            }
        )
        if degree_df.empty:
            return pd.DataFrame(columns=["gene_id", "reaction_count"])

        degree_df = degree_df.sort_values("reaction_count", ascending=False)
        return degree_df.reset_index(drop=True)

    def _create_reaction_type_plot(
        self,
        reaction_summary: dict[str, Any],
        *,
        plot_config: PlotConfig,
    ) -> go.Figure:
        """Generated: validation needed.

        Description:
            Create bar chart for key reaction-type counts.

        Args:
            reaction_summary (dict[str, Any]): Reaction summary dictionary.
            plot_config (PlotConfig): Plot configuration.

        Returns:
            go.Figure: Reaction type distribution plot.
        """
        labels = [
            "gprless_reaction_count",
            "reversible_reaction_count",
            "irreversible_reaction_count",
            "exchange_reaction_count",
        ]
        values = [int(reaction_summary[label]) for label in labels]

        figure = go.Figure(
            data=[
                go.Bar(
                    x=labels,
                    y=values,
                )
            ]
        )
        figure.update_layout(
            title="Reaction characterization after missing-gene processing",
            xaxis_title="Category",
            yaxis_title="Count",
            template="plotly_white",
            width=plot_config.width,
            height=plot_config.height,
        )
        return figure

    def _create_gene_reaction_degree_plot(
        self,
        gene_reaction_degree_df: pd.DataFrame,
        *,
        plot_config: PlotConfig,
    ) -> go.Figure:
        """Generated: validation needed.

        Description:
            Create histogram of gene reaction degree distribution.

        Args:
            gene_reaction_degree_df (pd.DataFrame): Gene degree summary table.
            plot_config (PlotConfig): Plot configuration.

        Returns:
            go.Figure: Degree distribution histogram.
        """
        if gene_reaction_degree_df.empty:
            histogram_input = [0]
        else:
            histogram_input = gene_reaction_degree_df["reaction_count"].astype(float).tolist()

        figure = go.Figure(
            data=[
                go.Histogram(
                    x=histogram_input,
                    nbinsx=40,
                )
            ]
        )
        figure.update_layout(
            title="Gene-to-reaction mapping degree distribution",
            xaxis_title="Reactions per gene",
            yaxis_title="Gene count",
            template="plotly_white",
            width=plot_config.width,
            height=plot_config.height,
        )
        return figure
