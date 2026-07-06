from typing import Any


class SortedSet:
    def __init__(self, iterable=None):
        self._set = set()
        if iterable is not None:
            self._set.update(iterable)
        self._sorted_list = sorted(self._set)

    def add(self, item):
        if item not in self._set:
            self._set.add(item)
            self._sorted_list.append(item)
            self._sorted_list.sort()

    def remove(self, item):
        if item in self._set:
            self._set.remove(item)
            self._sorted_list.remove(item)

    def __class_getitem__(cls, item: Any):
        return cls

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

    def sort(self, key=None, reverse=False):
        self._sorted_list.sort(key=key, reverse=reverse)
