from typing import Any

from VmaxBuilder.base.configs import InputSpec, OutputSpec


class DiagnosticsMixin:
    def before_run(self, scaffold): ...
    def after_run(self, scaffold): ...
    def on_error(self, error): ...


class BaseImplementation(DiagnosticsMixin):
    STAGE_NAME: str
    IMPL_NAME: str

    CONFIG_CLASS: type | None = None

    INPUTS: list[InputSpec] = []
    OUTPUTS: list[OutputSpec] = []

    CHILD_IMPLEMENTATIONS: dict[str, str] = {}

    def validate(self, scaffold: dict):
        for inp in self.INPUTS:
            if not inp.optional and inp.name not in scaffold:
                raise ValueError(f"Missing required input: {inp.name}")

    def run(self, scaffold: dict, config: Any) -> dict:
        raise NotImplementedError
