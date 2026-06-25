from VmaxBuilder.base.classes import BaseImplementation
from VmaxBuilder.stages import (
    DefaultExpressionImplementation,
    DefaultIrreversibleModelImplementation,
    ExpressionPTRImplementation,
)

registered_stages: dict[str, dict[str, type[BaseImplementation]]] = {
    "model": {
        "default": DefaultIrreversibleModelImplementation,
    },
    "protein": {
        "expression_only": DefaultExpressionImplementation,
        "expression_ptr": ExpressionPTRImplementation,
    },
}
