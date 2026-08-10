from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pandas as pd
from cobra import Model

from VmaxBuilder.base.classes import BaseImplementationDiagnostics, DiagnosticOutputSpec
from VmaxBuilder.base.configs import FullConfig, Scaffold
from VmaxBuilder.stages.protein.ptr.config import PTRInputConfig
from VmaxBuilder.stages.protein.ptr.ptr_utils import (
    resolve_special_gene_groups,
    transform_ptr_to_linear,
)
from VmaxBuilder.utils.custom_logging import CustomLogger
from VmaxBuilder.utils.plotting.colors import (
    COLORS_HEX,
    COLORS_RGB,
    custom_colorblind_color_discrete_palette,
    hex_to_rgb,
    rgb_to_hex,
    rgb_to_rgba,
    yield_discrete_colorblind_color,
)

COLORS = custom_colorblind_color_discrete_palette()
COLORBLIND_COLORS_RGB = COLORS[4]  # RGB format for Plotly


class GPRDiagnostics(BaseImplementationDiagnostics[FullConfig]):
    DIAGNOSTICS_NAME = "GPR Diagnostics"

    def __init__(
        self,
        full_config: FullConfig,
    ):
        self.logger = CustomLogger(f"{self.DIAGNOSTICS_NAME}")
        self.full_config = full_config

    def before_run(
        self,
        scaffold: Scaffold,
    ) -> dict[str, dict[str, Any]]:
        new_scaffold_objects = {
            "outputs": {},
            "diagnostics": {"GPR": []},
            "artifacts": {},
            "metadata": {},
        }
        # todo:
        return new_scaffold_objects

    def after_run(
        self,
        new_scaffold_objects: dict[str, dict[str, Any]],
        scaffold: Scaffold,
    ) -> dict[str, dict[str, Any]]:
        return {
            "outputs": {},
            "diagnostics": {"GPR": []},
            "artifacts": {},
            "metadata": {},
        }

        # todo:
        # IFP to gene distribution (amount of genes with x IFPs)
        # gene to IFP distribution (amount of IFPs with x genes)
        # IFP to reaction distribution (amount of reactions with x IFPs)
        # reaction to IFP distribution (amount of IFPs with x reactions)
        # gene to reactoin distribution (amount of reactions with x genes)
        # reaction to gene distribution (amount of genes with x reactions)
        # genes to GPR rule distribution (amount of GPR rules with x genes)
        # reactions to GPR rule distribution (amount of GPR rules with x reactions)
        # IFP to GPR rule distribution (amount of GPR rules with x IFPs)
        # GPR rule to IFP distribution (amount of IFPs with x GPR rules)
        # GPR rule to gene distribution (amount of genes with x GPR rules)
        # GPR_rule to gene distribution (amount of GPR rules with x genes)

        # Multi-Dimensional Scatter Plots (For Gene/IFP Characteristics)
        ## x axis: Number of GPR rules associated with the gene
        ## y axis: Number of reactions associated with the gene
        ## point size: Number of IFPs associated with the gene
        ## color = average size of associated IFPs

        # similarly for Reactions
        # x = number of genes
        # y = number of GPR rules
        # point size = number of IFPs rules
        # color = average size of associated IFPs

        # and for IFPS
        # x = nu]mber of unique GPR rules this IFP is associated with
        # y = number of reactions this IFP is associated with
        # point size = size of IFP
        #

        # layered sankey diagram with genes, IFPs, GPR rules, and reactions
