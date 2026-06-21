"""
Must be imported last for enum generation to work properly
"""

import importlib
import pkgutil
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

import VmaxBuilder.stages as stages_pkg
from VmaxBuilder.base.registry import STAGE_IMPLEMENTATIONS


def load_all_implementations():
    for _, module_name, _ in pkgutil.walk_packages(
        stages_pkg.__path__, stages_pkg.__name__ + "."
    ):
        print(f"Loading implementations from module: {module_name}")
        if module_name.endswith("implementation"):
            print(f"Loading implementations from module: {module_name}")
            importlib.import_module(module_name)


load_all_implementations()

print("Available implementations:", STAGE_IMPLEMENTATIONS)
print("Available model implementations:", STAGE_IMPLEMENTATIONS["model"])


MODEL_IMPLEMENTATIONS = StrEnum(
    "MODEL_IMPLEMENTATIONS", {name.lower(): name for name in STAGE_IMPLEMENTATIONS["model"]}
)
PROTEIN_IMPLEMENTATIONS = StrEnum(
    "PROTEIN_IMPLEMENTATIONS",
    {name.lower(): name for name in STAGE_IMPLEMENTATIONS["protein"]},
)
ALLOCATION_IMPLEMENTATIONS = StrEnum(
    "ALLOCATION_IMPLEMENTATIONS",
    {name.lower(): name for name in STAGE_IMPLEMENTATIONS["allocation"]},
)


class ImplementationContainer:
    def __init__(
        self,
    ):
        self.model = MODEL_IMPLEMENTATIONS
        self.protein = PROTEIN_IMPLEMENTATIONS
        self.allocation = ALLOCATION_IMPLEMENTATIONS


implementations = ImplementationContainer()
