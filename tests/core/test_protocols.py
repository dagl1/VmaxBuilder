from __future__ import annotations

from typing import Any

import pytest
from cobra import Model

from VmaxBuilder.config import APIConfig, StageName
from VmaxBuilder.config.validation import ConfigurationError
from VmaxBuilder.core import (
    DiagnosticsHookProtocol,
    Scaffold,
    StageProtocol,
    StrategyProtocol,
    get_scaffold_model,
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


def test_get_scaffold_model_returns_cobra_model_when_present() -> None:
    scaffold: Scaffold = {
        "inputs": {},
        "artifacts": {"model": Model("example")},
        "outputs": {},
        "metadata": {},
        "diagnostics": {},
        "extras": {},
    }

    assert isinstance(get_scaffold_model(scaffold), Model)


def test_get_scaffold_model_returns_none_when_optional() -> None:
    scaffold: Scaffold = {
        "inputs": {},
        "artifacts": {},
        "outputs": {},
        "metadata": {},
        "diagnostics": {},
        "extras": {},
    }

    assert get_scaffold_model(scaffold, required=False) is None


def test_get_scaffold_model_raises_for_missing_required_model() -> None:
    scaffold: Scaffold = {
        "inputs": {},
        "artifacts": {},
        "outputs": {},
        "metadata": {},
        "diagnostics": {},
        "extras": {},
    }

    with pytest.raises(ConfigurationError, match=r"artifacts\['model'\] missing"):
        get_scaffold_model(scaffold)


def test_get_scaffold_model_raises_for_invalid_artifact_type() -> None:
    scaffold: Scaffold = {
        "inputs": {},
        "artifacts": {"model": "not-model"},
        "outputs": {},
        "metadata": {},
        "diagnostics": {},
        "extras": {},
    }

    with pytest.raises(ConfigurationError, match="must be cobra.Model"):
        get_scaffold_model(scaffold)
