from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ImplementationProtocol(Protocol):
    STAGE_NAME: str
    IMPL_NAME: str

    CONFIG_CLASS: type | None
    CHILD_IMPLEMENTATIONS: dict[str, str]  # names, not classes

    def run(self, scaffold: dict, config: Any) -> dict: ...
