from __future__ import annotations

import warnings

import pytest

from VmaxBuilder.utils.custom_exceptions import (
    ExceptionIncorrectKwargs,
    SpecialTypeError,
    _check_and_return_value,
)


@pytest.mark.unit
def test_check_and_return_value_allows_optional_missing_value() -> None:
    result = _check_and_return_value({"mode": None}, "mode", ["OPTIONAL", "fast"])

    assert result is None


@pytest.mark.unit
def test_check_and_return_value_accepts_numeric_range() -> None:
    result = _check_and_return_value({"threshold": 3}, "threshold", [(1, 5)])

    assert result == 3


@pytest.mark.unit
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


@pytest.mark.unit
def test_exception_incorrect_kwargs_message_mentions_invalid_value() -> None:
    with pytest.raises(ExceptionIncorrectKwargs) as exception_info:
        _check_and_return_value({"mode": "invalid"}, "mode", ["fast", "slow"])

    assert "not a valid option" in str(exception_info.value)


@pytest.mark.unit
def test_check_and_return_value_any_sentinel_passes_all_values() -> None:
    result = _check_and_return_value({"key": "anything_at_all"}, "key", ["ANY"])
    assert result == "anything_at_all"


@pytest.mark.unit
def test_check_and_return_value_raises_when_key_missing_and_not_optional() -> None:
    with pytest.raises(ExceptionIncorrectKwargs, match="was not provided"):
        _check_and_return_value({}, "mode", ["fast", "slow"])


@pytest.mark.unit
def test_check_and_return_value_list_value_valid() -> None:
    result = _check_and_return_value({"items": ["a", "b"]}, "items", ["a", "b", "c"])
    assert result == ["a", "b"]


@pytest.mark.unit
def test_check_and_return_value_list_value_invalid_raises() -> None:
    with pytest.raises(ExceptionIncorrectKwargs, match="list"):
        _check_and_return_value({"items": ["a", "x"]}, "items", ["a", "b"])


@pytest.mark.unit
def test_check_and_return_value_numeric_tuple_out_of_range_raises() -> None:
    with pytest.raises(ExceptionIncorrectKwargs, match="must be between"):
        _check_and_return_value({"val": 10}, "val", [(0, 5)])


@pytest.mark.unit
def test_exception_incorrect_kwargs_numeric_case_message() -> None:
    exc = ExceptionIncorrectKwargs(
        key_name="val",
        get_value=99,
        options=[(0, 10)],
        special_case="numeric",
    )
    assert "must be between" in str(exc)


@pytest.mark.unit
def test_exception_incorrect_kwargs_list_case_message() -> None:
    exc = ExceptionIncorrectKwargs(
        key_name="items",
        get_value=["x"],
        options=["a", "b"],
        special_case="list",
    )
    assert "list" in str(exc)


@pytest.mark.unit
def test_special_type_error_includes_missing_arguments() -> None:
    exc = SpecialTypeError("Bad call", missing_arguments=["arg1", "arg2"])
    assert "arg1" in str(exc)
    assert "arg2" in str(exc)
    assert exc.missing_arguments == ["arg1", "arg2"]
