from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest

from VmaxBuilder.utils.extra_utils import (
    _deduplicate_preserve_order,
    _metabolite_has_same_formula,
    _metabolite_has_same_identifiers,
    _metabolite_has_same_names,
    check_if_string_or_integer,
    compare_dicts,
    convert_camel_case_to_snake_case,
    extract_compartment,
    is_effectively_integer,
    remove_compartment,
    resolve_gene_or_reaction_group_members,
)


def _make_met(
    id_: str,
    compartment: str,
    name: str = "",
    formula: str | None = None,
    charge: int | None = None,
) -> Any:
    """Helper to build a minimal metabolite-like namespace."""
    return SimpleNamespace(
        id=id_, compartment=compartment, name=name, formula=formula, charge=charge
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


# ---------------------------------------------------------------------------
# _metabolite_has_same_identifiers
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_metabolite_has_same_identifiers_matching() -> None:
    m1 = _make_met("ATP_c", "c")
    m2 = _make_met("ATP_c", "c")
    assert _metabolite_has_same_identifiers(m1, m2)


@pytest.mark.unit
def test_metabolite_has_same_identifiers_different() -> None:
    m1 = _make_met("ATP_c", "c")
    m2 = _make_met("ADP_c", "c")
    assert not _metabolite_has_same_identifiers(m1, m2)


# ---------------------------------------------------------------------------
# _metabolite_has_same_names
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_metabolite_has_same_names_matching_after_strip() -> None:
    m1 = _make_met("x", "c", name="  ATP  ")
    m2 = _make_met("y", "m", name="ATP")
    assert _metabolite_has_same_names(m1, m2)


@pytest.mark.unit
def test_metabolite_has_same_names_different() -> None:
    m1 = _make_met("x", "c", name="ATP")
    m2 = _make_met("y", "c", name="ADP")
    assert not _metabolite_has_same_names(m1, m2)


# ---------------------------------------------------------------------------
# _metabolite_has_same_formula
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_metabolite_has_same_formula_exact_match() -> None:
    m1 = _make_met("x", "c", formula="C10H15N5O10P2")
    m2 = _make_met("y", "c", formula="C10H15N5O10P2")
    assert _metabolite_has_same_formula(m1, m2)


@pytest.mark.unit
def test_metabolite_has_same_formula_none_returns_equal() -> None:
    m1 = _make_met("x", "c", formula=None)
    m2 = _make_met("y", "c", formula=None)
    assert _metabolite_has_same_formula(m1, m2)


@pytest.mark.unit
def test_metabolite_has_same_formula_ignore_h_plus_with_none_returns_false() -> None:
    m1 = _make_met("x", "c", formula=None)
    m2 = _make_met("y", "c", formula="C6H12O6")
    assert not _metabolite_has_same_formula(m1, m2, ignore_h_plus=True)


# ---------------------------------------------------------------------------
# _deduplicate_preserve_order
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_deduplicate_preserve_order_removes_duplicates() -> None:
    assert _deduplicate_preserve_order(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]


@pytest.mark.unit
def test_deduplicate_preserve_order_empty_list() -> None:
    assert _deduplicate_preserve_order([]) == []


# ---------------------------------------------------------------------------
# resolve_gene_or_reaction_group_members
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolve_gene_or_reaction_group_members_no_model_passthrough() -> None:
    result = resolve_gene_or_reaction_group_members(None, ["GENE1", "GENE2"])
    assert result == ["GENE1", "GENE2"]


@pytest.mark.unit
def test_resolve_gene_or_reaction_group_members_filters_by_expression_ids() -> None:
    result = resolve_gene_or_reaction_group_members(
        None, ["GENE1", "GENE2", "GENE3"], expression_gene_ids={"GENE1", "GENE3"}
    )
    assert result == ["GENE1", "GENE3"]


@pytest.mark.unit
def test_resolve_gene_or_reaction_group_members_with_model_expands_reaction() -> None:
    gene_a = SimpleNamespace(id="GENE_A")
    gene_b = SimpleNamespace(id="GENE_B")
    reaction = SimpleNamespace(id="RXN1", genes=[gene_a, gene_b], gene_reaction_rule="GENE_A")
    model = SimpleNamespace(reactions=[reaction])

    result = resolve_gene_or_reaction_group_members(model, ["RXN1"])
    assert "GENE_A" in result
    assert "GENE_B" in result


# ---------------------------------------------------------------------------
# convert_camel_case_to_snake_case edge cases
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_convert_camel_case_to_snake_case_empty_string() -> None:
    assert convert_camel_case_to_snake_case("") == ""


@pytest.mark.unit
def test_convert_camel_case_to_snake_case_already_lowercase() -> None:
    assert convert_camel_case_to_snake_case("lowercase") == "lowercase"


# ---------------------------------------------------------------------------
# compare_dicts (smoke test: function should not raise)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_compare_dicts_equal_dicts_does_not_raise(capsys: pytest.CaptureFixture) -> None:
    compare_dicts({"a": 1}, {"a": 1})
    out = capsys.readouterr().out
    assert "equal" in out.lower()


@pytest.mark.unit
def test_compare_dicts_different_dicts_prints_diff(capsys: pytest.CaptureFixture) -> None:
    compare_dicts({"a": 1, "b": 2}, {"a": 9, "c": 3})
    out = capsys.readouterr().out
    assert "differ" in out.lower() or "b" in out or "c" in out


# ---------------------------------------------------------------------------
# extract_compartment edge cases
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_extract_compartment_bracket_form() -> None:
    assert extract_compartment("MAM20065[c]") == "c"


@pytest.mark.unit
def test_extract_compartment_no_compartment_returns_empty() -> None:
    assert extract_compartment("plainid") == ""


@pytest.mark.unit
def test_extract_compartment_non_string_returns_empty() -> None:
    assert extract_compartment(123) == ""  # type: ignore[arg-type]
