from __future__ import annotations

import pandas as pd
import pytest

from VmaxBuilder.utils.extra_utils import (
    check_if_string_or_integer,
    convert_camel_case_to_snake_case,
    extract_compartment,
    is_effectively_integer,
    remove_compartment,
)


@pytest.mark.unit
def test_extract_and_remove_compartment_from_identifier() -> None:
    identifier = "MAM20065_cyt"

    assert extract_compartment(identifier) == "cyt"
    assert remove_compartment(identifier) == "MAM20065"


@pytest.mark.unit
def test_convert_camel_case_to_snake_case() -> None:
    assert convert_camel_case_to_snake_case("camelCaseName") == "camel_case_name"


@pytest.mark.unit
def test_is_effectively_integer_accepts_integer_like_values() -> None:
    assert is_effectively_integer("3.0")
    assert not is_effectively_integer("3.2")


@pytest.mark.unit
def test_check_if_string_or_integer_detects_mixed_series() -> None:
    series = pd.Series(["abc", "123", "45"])

    assert check_if_string_or_integer(series)
