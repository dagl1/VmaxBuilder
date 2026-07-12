from VmaxBuilder.base.classes import BaseImplementation
from VmaxBuilder.typing_stubs.protein.expressionPTR.implementation import (
    ExpressionPTRConfigProtocol,
)


class SimplePTRMultiplicationImplementation(BaseImplementation[ExpressionPTRConfigProtocol]):
    def __init__(self, ptr):
        self.ptr = ptr
