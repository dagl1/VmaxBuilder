"""Generated: validation needed.

Description:
    Shared enums for refactored VmaxBuilder configuration and API contracts.
"""

from __future__ import annotations

from enum import Enum
from functools import wraps
from typing import Any, Callable, Sequence, TypeVar


class ValidationMode(str, Enum):
    """Generated: validation needed.

    Description:
        Validation strictness mode for config fields and stage-local checks.
    """

    STRICT = "strict"
    LENIENT = "lenient"


class StageName(str, Enum):
    """Generated: validation needed.

    Description:
        Stable top-level stage names for refactored orchestrator execution.
    """

    MODEL = "model"
    GPR = "gpr"
    PROTEIN = "protein"
    KCAT = "kcat"
    ALLOCATION = "allocation"
    VMAX = "vmax"


class DiagnosticSeverity(str, Enum):
    """Generated: validation needed.

    Description:
        Severity levels used by diagnostics runner and stage-level failure policy.
    """

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class KcatLevel(str, Enum):
    """Generated: validation needed.

    Description:
        Canonical kcat representation levels used by conversion pipeline.
    """

    GENE_SUBSTRATE = "L1"
    GENE_REACTION = "L2"
    IFP_SUBSTRATE = "L3"
    IFP_REACTION = "L4"


class ProteinSourceMode(str, Enum):
    """Generated: validation needed.

    Description:
        Supported top-level protein abundance source modes.
    """

    EXPRESSION_PTR = "expression_ptr"
    PROTEOMICS = "proteomics"


class LoadResolutionMode(str, Enum):
    """Generated: validation needed.

    Description:
        File loading resolution order used by loading policy.
    """

    EXACT_PATH = "exact_path"
    DISCOVER = "discover"
    EXACT_THEN_DISCOVER = "exact_then_discover"


class ReactionNotation(str, Enum):
    """Generated: validation needed.

    Description:
        Reaction notation convention used for model reaction identifiers.
    """

    STANDARD = "standard"
    ALTERNATIVE = "alternative"


class PrimaryOutputFormat(str, Enum):
    """Generated: validation needed.

    Description:
        Primary artifact table format for generated Vmax results.
    """

    FEATHER = "feather"
