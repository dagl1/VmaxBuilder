"""Pytest configuration and shared fixtures for VmaxBuilder tests.

This module provides:
- Test markers for unit, integration, and usability tests
- Shared fixtures for common test scenarios
- Test data paths
- Logging configuration for test runs
"""

import logging
from pathlib import Path

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Test data paths
# ─────────────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent
TEST_DATA_DIR = PROJECT_ROOT / "data" / "tests"
TEST_FIXTURES_DIR = TEST_DATA_DIR / "fixtures"


# ─────────────────────────────────────────────────────────────────────────────
# Pytest hooks and configuration
# ─────────────────────────────────────────────────────────────────────────────


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "unit: Unit tests for individual functions and components"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests for module interactions"
    )
    config.addinivalue_line(
        "markers", "usability: Usability/workflow tests with realistic data"
    )
    config.addinivalue_line("markers", "slow: Tests that take longer to run")
    config.addinivalue_line(
        "markers", "requires_data: Tests that require external data fixtures"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Shared fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def test_data_dir() -> Path:
    """Return path to test data directory.

    Returns:
        Path: Absolute path to `data/tests/`.
    """
    return TEST_DATA_DIR


@pytest.fixture
def test_fixtures_dir() -> Path:
    """Return path to test fixtures directory.

    Returns:
        Path: Absolute path to `data/tests/fixtures/`.
    """
    return TEST_FIXTURES_DIR


@pytest.fixture
def caplog_with_level(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    """Fixture to capture logs at DEBUG level.

    Args:
        caplog: Standard pytest log capture fixture.

    Returns:
        pytest.LogCaptureFixture: Log capture at DEBUG level.
    """
    caplog.set_level(logging.DEBUG)
    return caplog
