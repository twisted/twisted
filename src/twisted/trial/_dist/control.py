# -*- test-case-name: twisted.trial._dist.test.test_bracket -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
A library for control flow functionality.
"""

from typing import Awaitable, Callable, TypeVar, Union, cast

_A = TypeVar("_A")
_B = TypeVar("_B")
_C = TypeVar("_C")


async def bracket(
    first: Callable[[], Union[_A, Awaitable[_A]]],
    last: Callable[[], Union[_B, Awaitable[_B]]],
    between: Callable[[], Union[_C, Awaitable[_C]]],
) -> _C:
    """
    Invoke an action between two other actions.

    This is a functional version of C{async with ...} that is convenient to
    use when setup and teardown are already defined as functions, when a
    partially applied form of the async context manager is useful, and for
    other functional-style composition purposes.

    @param first: A no-argument function that may return a Deferred.  It is
        called first.

    @param between: A no-argument function that may return a Deferred.  It is
        called after C{first} is done and completes before C{last} is called.

    @param last: A no-argument function that may return a Deferred.  It is
        called last.

    @return: An awaitable which completes with the result of C{between}.
    """
    x = first()
    if isinstance(x, Awaitable):
        await x
    try:
        result = between()
        if isinstance(result, Awaitable):
            return await cast(Awaitable[_C], result)
        return result
    finally:
        y = last()
        if isinstance(y, Awaitable):
            await y
