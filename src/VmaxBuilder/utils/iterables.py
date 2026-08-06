from typing import Any, Generic, TypeVar

T = TypeVar("T")


class SortedSet(set, Generic[T]):
    def __init__(
        self,
        iterable=None,
    ):
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

    def sort(self, key=None, reverse=False):
        self._sorted_list.sort(key=key, reverse=reverse)

    # def __class_getitem__(cls, item: Any):
    #     return cls

    def __contains__(self, item):
        return item in self._set

    def __iter__(self):
        return iter(self._sorted_list)

    def __len__(self):
        return len(self._set)

    def __repr__(self):
        return f"SortedSet({self._sorted_list})"

    def __eq__(self, other):
        if isinstance(other, SortedSet):
            return self._set == other._set
        return False

    def __ne__(self, other):
        return not self.__eq__(other)


def make_json_serializable(obj):
    if isinstance(obj, (SortedSet, set)):
        return list(obj)
    elif isinstance(obj, dict):
        return {key: make_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [make_json_serializable(value) for value in obj]
    else:
        return obj
