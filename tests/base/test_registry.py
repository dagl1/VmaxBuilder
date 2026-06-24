from __future__ import annotations

from dataclasses import dataclass

import pytest

from VmaxBuilder.base.registry import (
    IMPLEMENTATION_REGISTRY,
    STAGE_IMPLEMENTATIONS,
    get_available_implementations,
    get_available_stages,
    get_implementation_config_class,
    get_implementation_info,
    register_implementation,
)


@pytest.fixture(autouse=True)
def reset_registry_state():
    registry_backup = IMPLEMENTATION_REGISTRY.copy()
    stage_backup = {key: value[:] for key, value in STAGE_IMPLEMENTATIONS.items()}

    IMPLEMENTATION_REGISTRY.clear()
    STAGE_IMPLEMENTATIONS.clear()
    try:
        yield
    finally:
        IMPLEMENTATION_REGISTRY.clear()
        IMPLEMENTATION_REGISTRY.update(registry_backup)

        STAGE_IMPLEMENTATIONS.clear()
        for key, value in stage_backup.items():
            STAGE_IMPLEMENTATIONS[key] = value


@pytest.mark.unit
def test_register_implementation_adds_to_registry_and_stage_lookup() -> None:
    @register_implementation("model", "demo")
    class _Implementation:
        pass

    assert IMPLEMENTATION_REGISTRY["model:demo"] is _Implementation
    assert "demo" in STAGE_IMPLEMENTATIONS["model"]
    assert _Implementation.STAGE_NAME == "model"  # type: ignore[attr-defined]
    assert _Implementation.IMPL_NAME == "demo"  # type: ignore[attr-defined]


@pytest.mark.unit
def test_get_available_stages_returns_sorted_unique_values() -> None:
    @register_implementation("protein", "alpha")
    class _Protein:
        pass

    @register_implementation("model", "beta")
    class _Model:
        pass

    assert get_available_stages() == ["model", "protein"]


@pytest.mark.unit
def test_get_available_implementations_returns_sorted_names_for_stage() -> None:
    @register_implementation("model", "zeta")
    class _Zeta:
        pass

    @register_implementation("model", "alpha")
    class _Alpha:
        pass

    assert get_available_implementations("model") == ["alpha", "zeta"]


@pytest.mark.unit
def test_get_implementation_info_returns_expected_payload() -> None:
    @dataclass
    class _Config:
        threshold: int = 1

    @register_implementation("model", "payload")
    class _Payload:
        CONFIG_CLASS = _Config
        CHILD_IMPLEMENTATIONS = {}

    info = get_implementation_info("model", "payload")

    assert info["stage"] == "model"
    assert info["name"] == "payload"
    assert info["class"] is _Payload
    assert info["config_class"] is _Config


@pytest.mark.unit
def test_get_implementation_info_raises_for_missing_key() -> None:
    with pytest.raises(
        ValueError,
        match="Implementation 'missing' for stage 'model' not found",
    ):
        get_implementation_info("model", "missing")


@pytest.mark.unit
def test_get_implementation_config_class_returns_registered_class() -> None:
    @dataclass
    class _Config:
        enabled: bool = True

    @register_implementation("model", "cfg")
    class _WithConfig:
        CONFIG_CLASS = _Config

    config_class = get_implementation_config_class("model", "cfg")

    assert config_class is _Config
