from collections.abc import Set
from pathlib import PosixPath
from typing import Generic, Iterable, Optional, TypeVar

import pandas as pd

T = TypeVar("T")


class SortedSet(Set, Generic[T]):
    def __init__(self, iterable: Optional[Iterable[T]] = None):
        self._set = set()
        if iterable is not None:
            self._set.update(iterable)
        self._sorted_list = sorted(self._set)

    def add(self, item: T):
        if item not in self._set:
            self._set.add(item)
            self._sorted_list.append(item)
            self._sorted_list.sort()

    def remove(self, item: T):
        if item in self._set:
            self._set.remove(item)
            self._sorted_list.remove(item)

    def update(self, iterable: Iterable[T]):
        self._set.update(iterable)
        self._sorted_list = sorted(self._set)

    def sort(self, key=None, reverse=False):
        self._sorted_list.sort(key=key, reverse=reverse)

    def __contains__(self, item: object) -> bool:
        return item in self._set

    def __iter__(self):
        return iter(self._sorted_list)

    def __len__(self) -> int:
        return len(self._set)

    def __repr__(self) -> str:
        return f"SortedSet({self._sorted_list})"

    def union(self, other: Iterable[T]) -> "SortedSet[T]":
        if isinstance(other, SortedSet):
            return SortedSet(self._set.union(other._set))
        return SortedSet(self._set.union(other))

    def __or__(self, other: Iterable[T]) -> "SortedSet[T]":
        return self.union(other)


def make_json_serializable(obj):
    try:
        from VmaxBuilder.stages.Kcat.Kcat_utils import (
            GeneMainSubstratePrediction,
            GeneSubstratePrediction,
            ReactionMainSubstratePrediction,
        )

        prediction_types = (
            ReactionMainSubstratePrediction,
            GeneMainSubstratePrediction,
            GeneSubstratePrediction,
        )
    except ModuleNotFoundError:
        prediction_types = ()

    if isinstance(obj, (SortedSet, set)):
        return list(obj)
    elif isinstance(obj, dict):
        return {key: make_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [make_json_serializable(value) for value in obj]
    elif isinstance(obj, PosixPath):
        return str(obj)
    elif isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient="records")
    elif isinstance(obj, pd.Series):
        return obj.to_dict()
    elif prediction_types and isinstance(obj, prediction_types):
        return obj.to_dict()

    else:
        return obj
