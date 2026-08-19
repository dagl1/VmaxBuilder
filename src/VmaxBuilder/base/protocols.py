from typing import Protocol, runtime_checkable


@runtime_checkable
class DependencyChecker(Protocol):
    def __call__(self, *args, **kwargs) -> bool:
        """Check if the dependencies are satisfied."""
        ...
