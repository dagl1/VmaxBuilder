from __future__ import annotations

import warnings

import pytest

from VmaxBuilder.utils.custom_exceptions import (
    ExceptionIncorrectKwargs,
    _check_and_return_value,
)


def test_check_and_return_value_allows_optional_missing_value() -> None:
    result = _check_and_return_value({"mode": None}, "mode", ["OPTIONAL", "fast"])

    assert result is None


def test_check_and_return_value_accepts_numeric_range() -> None:
    result = _check_and_return_value({"threshold": 3}, "threshold", [(1, 5)])

    assert result == 3


def test_check_and_return_value_warns_when_ignore_missing_options() -> None:
    with warnings.catch_warnings(record=True) as captured_warnings:
        warnings.simplefilter("always")
        result = _check_and_return_value(
            {},
            "mode",
            ["fast", "slow"],
            ignore_missing_options=True,
        )

    assert result is None
    assert captured_warnings
    assert "Ignoring missing options" in str(captured_warnings[0].message)


def test_exception_incorrect_kwargs_message_mentions_invalid_value() -> None:
    with pytest.raises(ExceptionIncorrectKwargs) as exception_info:
        _check_and_return_value({"mode": "invalid"}, "mode", ["fast", "slow"])

    assert "not a valid option" in str(exception_info.value)
