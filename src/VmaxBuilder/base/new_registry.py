from dataclasses import dataclass

from VmaxBuilder.base.classes import BaseImplementation
from VmaxBuilder.stages import (
    DefaultExpressionImplementation,
    DefaultIrreversibleModelImplementation,
    ExpressionPTRImplementation,
)


@dataclass(frozen=True)
class ModelStageRegistry:
    default: type[DefaultIrreversibleModelImplementation] = (
        DefaultIrreversibleModelImplementation
    )


@dataclass(frozen=True)
class ProteinStageRegistry:
    expression_only: type[DefaultExpressionImplementation] = DefaultExpressionImplementation
    expression_ptr: type[ExpressionPTRImplementation] = ExpressionPTRImplementation


@dataclass(frozen=True)
class StageRegistry:
    model: ModelStageRegistry = ModelStageRegistry()
    protein: ProteinStageRegistry = ProteinStageRegistry()


stage_registry = StageRegistry()
