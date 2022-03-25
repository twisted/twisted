from dataclasses import dataclass, field
from itertools import count
from typing import (
    Callable,
    Dict,
    FrozenSet,
    Generic,
    Iterable,
    Iterator,
    Set,
    Tuple,
    TypeVar,
)

from twisted.internet.defer import Deferred

T = TypeVar("T")


@dataclass
class CallWhenAll(Generic[T]):
    _call: Callable[[], None]
    _required: FrozenSet[T]
    _present: Set[T] = field(default_factory=set)
    _called: bool = False

    def check(self, checks: Iterable[Tuple[bool, T]]) -> None:
        for shouldAdd, item in sorted(checks, key=lambda x: x[0]):
            method = self.add if shouldAdd else self.remove
            method(item)

    def add(self, item: T) -> None:
        if item in self._present:
            return
        self._present.add(item)
        if self._called:
            return
        remaining = self._required - self._present
        if not remaining:
            self._called = True
            self._call()

    def remove(self, item: T) -> None:
        if item not in self._present:
            return
        self._present.remove(item)


AttemptId = int


@dataclass
class Outstanding(Generic[T]):
    _ds: Dict[int, Deferred[T]] = field(default_factory=dict)
    _id: Iterator[AttemptId] = field(default_factory=count)

    def add(self, d: Deferred[T]) -> Deferred[T]:
        nextId = next(self._id)
        self._ds[nextId] = d

        def done(result: T) -> T:
            del self._ds[nextId]
            return result

        return d.addBoth(done)

    def cancel(self) -> None:
        while self._ds:
            k, v = self._ds.popitem()
            v.cancel()

    def empty(self) -> bool:
        return len(self._ds) == 0
