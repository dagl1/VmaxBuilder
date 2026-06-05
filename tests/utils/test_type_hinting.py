"""Tests for VmaxBuilder.utils.type_hinting."""

from __future__ import annotations

import pytest

from VmaxBuilder.utils.type_hinting import (
    TypeNode,
    UnionNode,
    _infer_type,
    _merge_types,
    _render_type,
    parse_type_hint,
)

# ---------------------------------------------------------------------------
# _merge_types
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_merge_types_single_element_returns_node_directly() -> None:
    node = TypeNode("int")
    result = _merge_types({node})
    assert result is node


@pytest.mark.unit
def test_merge_types_multiple_elements_returns_union_node() -> None:
    nodes = {TypeNode("int"), TypeNode("str")}
    result = _merge_types(nodes)
    assert isinstance(result, UnionNode)
    assert len(result.members) == 2


# ---------------------------------------------------------------------------
# _infer_type
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "value, expected_name",
    [
        (None, "None"),
        (True, "bool"),
        (42, "int"),
        (3.14, "float"),
        ("hello", "str"),
    ],
)
def test_infer_type_scalar_types(value: object, expected_name: str) -> None:
    result = _infer_type(value)
    assert isinstance(result, TypeNode)
    assert result.name == expected_name


@pytest.mark.unit
def test_infer_type_empty_list_returns_list_of_any() -> None:
    result = _infer_type([])
    assert isinstance(result, TypeNode)
    assert result.name == "List"
    assert result.args[0] == TypeNode("Any")


@pytest.mark.unit
def test_infer_type_homogeneous_list() -> None:
    result = _infer_type([1, 2, 3])
    assert isinstance(result, TypeNode)
    assert result.name == "List"
    assert result.args[0] == TypeNode("int")


@pytest.mark.unit
def test_infer_type_empty_dict_returns_dict_of_any() -> None:
    result = _infer_type({})
    assert isinstance(result, TypeNode)
    assert result.name == "Dict"


@pytest.mark.unit
def test_infer_type_homogeneous_dict() -> None:
    result = _infer_type({"a": 1, "b": 2})
    assert isinstance(result, TypeNode)
    assert result.name == "Dict"
    assert result.args[0] == TypeNode("str")
    assert result.args[1] == TypeNode("int")


@pytest.mark.unit
def test_infer_type_empty_set_returns_set_of_any() -> None:
    result = _infer_type(set())
    assert isinstance(result, TypeNode)
    assert result.name == "Set"


@pytest.mark.unit
def test_infer_type_tuple() -> None:
    result = _infer_type((1, "a"))
    assert isinstance(result, TypeNode)
    assert result.name == "Tuple"
    assert len(result.args) == 2


@pytest.mark.unit
def test_infer_type_empty_tuple() -> None:
    result = _infer_type(())
    assert isinstance(result, TypeNode)
    assert result.name == "Tuple"
    assert result.args == ()


@pytest.mark.unit
def test_infer_type_unknown_object_uses_class_name() -> None:
    class Exotic:
        pass

    result = _infer_type(Exotic())
    assert isinstance(result, TypeNode)
    assert result.name == "Exotic"


# ---------------------------------------------------------------------------
# _render_type
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_render_type_simple_node() -> None:
    assert _render_type(TypeNode("int")) == "int"


@pytest.mark.unit
def test_render_type_node_with_args() -> None:
    node = TypeNode("List", (TypeNode("int"),))
    assert _render_type(node) == "List[int]"


@pytest.mark.unit
def test_render_type_union_node_pipe_syntax() -> None:
    union = UnionNode(frozenset({TypeNode("int"), TypeNode("str")}))
    result = _render_type(union, use_Union=False)
    assert "int" in result and "str" in result and "|" in result


@pytest.mark.unit
def test_render_type_union_node_union_syntax() -> None:
    union = UnionNode(frozenset({TypeNode("int"), TypeNode("str")}))
    result = _render_type(union, use_Union=True)
    assert result.startswith("Union[")
    assert "int" in result and "str" in result


# ---------------------------------------------------------------------------
# parse_type_hint (public API)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_parse_type_hint_returns_string_for_int(capsys: pytest.CaptureFixture) -> None:
    result = parse_type_hint(42)
    assert result == "int"
    captured = capsys.readouterr()
    assert "int" in captured.out


@pytest.mark.unit
def test_parse_type_hint_list_of_str(capsys: pytest.CaptureFixture) -> None:
    result = parse_type_hint(["a", "b"])
    assert result == "List[str]"


@pytest.mark.unit
def test_parse_type_hint_use_union_syntax(capsys: pytest.CaptureFixture) -> None:
    result = parse_type_hint([1, "x"], use_Union=True)
    assert "Union" in result


@pytest.mark.unit
def test_parse_type_hint_nested_dict(capsys: pytest.CaptureFixture) -> None:
    result = parse_type_hint({"key": [1, 2]})
    assert "Dict" in result
    assert "List" in result
