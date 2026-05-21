from __future__ import annotations

from typing import Any

from VmaxBuilder.config import APIConfig, StageName
from VmaxBuilder.core import (
    DiagnosticsHookProtocol,
    Scaffold,
    StageProtocol,
    StrategyProtocol,
)


class _StageImplementation:
    name = StageName.MODEL

    def run(self, scaffold: Scaffold, config: APIConfig) -> Scaffold:
        scaffold["metadata"]["stage"] = config.model.reaction_notation.value
        return scaffold


class _StrategyImplementation:
    method_key = "example"

    def run(self, scaffold: Scaffold, config: APIConfig) -> Scaffold:
        scaffold["extras"]["method"] = config.protein.source_mode.value
        return scaffold


class _DiagnosticsHookImplementation:
    stage = StageName.PROTEIN
    name = "protein-hook"

    def before_stage(
        self,
        scaffold: Scaffold,
        *,
        config: APIConfig,
        method_key: str | None = None,
    ) -> tuple[dict[str, Any], ...]:
        return ()

    def after_stage(
        self,
        scaffold: Scaffold,
        *,
        config: APIConfig,
        method_key: str | None = None,
    ) -> tuple[dict[str, Any], ...]:
        return ()


def test_stage_protocol_is_runtime_checkable() -> None:
    assert isinstance(_StageImplementation(), StageProtocol)


def test_strategy_protocol_is_runtime_checkable() -> None:
    assert isinstance(_StrategyImplementation(), StrategyProtocol)


def test_diagnostics_hook_protocol_is_runtime_checkable() -> None:
    assert isinstance(_DiagnosticsHookImplementation(), DiagnosticsHookProtocol)
