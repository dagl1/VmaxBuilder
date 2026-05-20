from __future__ import annotations

import pandas as pd

from VmaxBuilder.utils.extra_utils import (
    check_if_string_or_integer,
    convert_camel_case_to_snake_case,
    extract_compartment,
    is_effectively_integer,
    remove_compartment,
)


def test_extract_and_remove_compartment_from_identifier() -> None:
    identifier = "MAM20065_cyt"

    assert extract_compartment(identifier) == "cyt"
    assert remove_compartment(identifier) == "MAM20065"


def test_convert_camel_case_to_snake_case() -> None:
    assert convert_camel_case_to_snake_case("camelCaseName") == "camel_case_name"


def test_is_effectively_integer_accepts_integer_like_values() -> None:
    assert is_effectively_integer("3.0")
    assert not is_effectively_integer("3.2")


def test_check_if_string_or_integer_detects_mixed_series() -> None:
    series = pd.Series(["abc", "123", "45"])

    assert check_if_string_or_integer(series)
