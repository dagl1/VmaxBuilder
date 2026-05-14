"""
This module contains type hinting utilities for the SWAMP project. These include ready-made Union types to be imported,
as well as custom type hints for commonly used data structures within the project. It also includes a function used in
development and debugigng for checking the necessary type hint for an object.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Tuple, Union

# create a list or dict type hint
ListOrDict = Union[List[Any], Dict[Any, Any]]


@dataclass(frozen=True)
class TypeNode:
    name: str
    args: Tuple[Union["TypeNode", "UnionNode"], ...] = ()


@dataclass(frozen=True)
class UnionNode:
    members: FrozenSet[TypeNode]


def _merge_types(types: set) -> UnionNode:
    if len(types) == 1:
        return next(iter(types))
    return UnionNode(frozenset(types))


def _infer_type(obj):
    if obj is None:
        return TypeNode("None")

    if isinstance(obj, bool):
        return TypeNode("bool")

    if isinstance(obj, int):
        return TypeNode("int")

    if isinstance(obj, float):
        return TypeNode("float")

    if isinstance(obj, str):
        return TypeNode("str")

    if isinstance(obj, Mapping):
        if not obj:
            return TypeNode("Dict", (TypeNode("Any"), TypeNode("Any")))

        key_types = {_infer_type(k) for k in obj.keys()}
        value_types = {_infer_type(v) for v in obj.values()}

        return TypeNode(
            "Dict",
            (
                _merge_types(key_types),
                _merge_types(value_types),
            ),
        )

    if isinstance(obj, list):
        if not obj:
            return TypeNode("List", (TypeNode("Any"),))

        elem_types = {_infer_type(e) for e in obj}
        return TypeNode(
            "List",
            (_merge_types(elem_types),),
        )
    elif isinstance(obj, set):
        if not obj:
            return TypeNode("Set", (TypeNode("Any"),))

        elem_types = {_infer_type(e) for e in obj}
        return TypeNode(
            "Set",
            (_merge_types(elem_types),),
        )
    elif isinstance(obj, tuple):
        if not obj:
            return TypeNode("Tuple", ())

        elem_types = tuple(_infer_type(e) for e in obj)
        return TypeNode(
            "Tuple",
            elem_types,
        )

    return TypeNode(type(obj).__name__)


def _render_type(node, *, use_Union: bool = False) -> str:
    if isinstance(node, UnionNode):
        members = sorted((_render_type(m, use_Union=use_Union) for m in node.members))
        if use_Union:
            return_string = f"Union[{', '.join(members)}]"
        else:
            return_string = " | ".join(members)
    elif not node.args:
        return_string = node.name
    else:
        return_string = (
            f"{node.name}"
            f"[{', '.join(_render_type(a, use_Union=use_Union) for a in node.args)}]"
        )

    return return_string


def parse_type_hint(_object: object, *, use_Union: bool = False) -> str:
    """
    Infer and render the type hint for a given object.
    Args:
        _object (object): The object to infer the type hint for.

        use_Union (Optional[bool]): Whether to use 'Union' syntax instead of '|'.

    Returns:
        return_string (str): The inferred type hint as a string.
    """
    inferred = _infer_type(_object)
    return_string = _render_type(inferred, use_Union=use_Union)
    print(return_string)
    return return_string


if __name__ == "__main__":
    data = [
        {
            "id": 1,
            "scores": [1.2, 3.4],
        },
        {
            "id": 2,
            1: ("a", "b"),
        },
    ]
    parse_type_hint(data)
    data_2 = {
        "name": "example",
        "values": {1, 2, 3.5, None},
        "attributes": {"key1": True, "key2": 42},
        10: (
            1,
            2,
            {
                1: "a",
                2: "b",
                "string_key": [1, 2, 3],
            },
        ),
    }
    data_3 = {
        "dict_key": {
            "nested_list": [
                {"inner_dict": {"a": 1, "b": 2}},
                {"inner_dict": {"c": 3.5, "d": None}},
            ],
            "nested_set": {frozenset({1, 2}), frozenset({3, 4})},
            "inter_tuple": (1, 2, 3),
            "int": 42,
        },
    }
    parse_type_hint(data_2)
    parse_type_hint(data_3)
