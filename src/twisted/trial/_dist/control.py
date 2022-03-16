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

    :param first: A no-argument function that may return a Deferred.  It is
        called first.

    :param between: A no-argument function that may return a Deferred.  It is
        called after ``first`` is done and completes before ``last`` is called.

    :param last: A no-argument function that may return a Deferred.  It is
        called last.

    :return Deferred: A ``Deferred`` which fires with the result of
        ``between``.
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
