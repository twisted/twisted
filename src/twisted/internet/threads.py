# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Extended thread dispatching support.

For basic support see reactor threading API docs.
"""

from __future__ import annotations

import queue as Queue
from typing import Callable, TypeVar

from typing_extensions import ParamSpec

from twisted.internet.defer import Deferred, maybeDeferred
from twisted.internet.interfaces import IReactorFromThreads, IReactorThreads
from twisted.internet.reactors import getGlobal
from twisted.python import failure
from twisted.python.failure import Failure
from twisted.python.threadpool import ThreadPool

_P = ParamSpec("_P")
_R = TypeVar("_R")


def deferToThreadPool(
    reactor: IReactorFromThreads,
    threadpool: ThreadPool,
    f: Callable[_P, _R],
    *args: _P.args,
    **kwargs: _P.kwargs,
) -> Deferred[_R]:
    """
    Call the function C{f} using a thread from the given threadpool and return
    the result as a Deferred.

    This function is only used by client code which is maintaining its own
    threadpool.  To run a function in the reactor's threadpool, use
    C{deferToThread}.

    @param reactor: The reactor in whose main thread the Deferred will be
        invoked.

    @param threadpool: An object which supports the C{callInThreadWithCallback}
        method of C{twisted.python.threadpool.ThreadPool}.

    @param f: The function to call.
    @param args: positional arguments to pass to f.
    @param kwargs: keyword arguments to pass to f.

    @return: A Deferred which fires a callback with the result of f, or an
        errback with a L{twisted.python.failure.Failure} if f throws an
        exception.
    """
    d: Deferred[_R] = Deferred()

    def onResult(success: bool, result: _R | BaseException) -> None:
        if success:
            reactor.callFromThread(d.callback, result)
        else:
            reactor.callFromThread(d.errback, result)

    threadpool.callInThreadWithCallback(onResult, f, *args, **kwargs)

    return d


def deferToThread(
    f: Callable[_P, _R], *args: _P.args, **kwargs: _P.kwargs
) -> Deferred[_R]:
    """
    Run a function in a thread and return the result as a Deferred.

    @param f: The function to call.
    @param args: positional arguments to pass to f.
    @param kwargs: keyword arguments to pass to f.

    @return: A Deferred which fires a callback with the result of f,
    or an errback with a L{twisted.python.failure.Failure} if f throws
    an exception.
    """
    reactor = getGlobal(IReactorThreads)
    return deferToThreadPool(reactor, reactor.getThreadPool(), f, *args, **kwargs)


def _runMultiple(tupleList):
    """
    Run a list of functions.
    """
    for f, args, kwargs in tupleList:
        f(*args, **kwargs)


def callMultipleInThread(tupleList):
    """
    Run a list of functions in the same thread.

    tupleList should be a list of (function, argsList, kwargsDict) tuples.
    """
    getGlobal(IReactorThreads).callInThread(_runMultiple, tupleList)


def blockingCallFromThread(
    reactor: IReactorThreads, f: Callable[_P, _R], *a: _P.args, **kw: _P.kwargs
) -> _R:
    """
    Run a function in the reactor from a thread, and wait for the result
    synchronously.  If the function returns a L{Deferred}, wait for its result
    and return that.

    @param reactor: The L{IReactorThreads} provider which will be used to
        schedule the function call.

    @param f: the callable to run in the reactor thread
    @type f: any callable.

    @param a: the arguments to pass to C{f}.

    @param kw: the keyword arguments to pass to C{f}.

    @return: the result of the L{Deferred} returned by C{f}, or the result of
        C{f} if it returns anything other than a L{Deferred}.

    @raise Exception: If C{f} raises a synchronous exception,
        C{blockingCallFromThread} will raise that exception.  If C{f} returns a
        L{Deferred} which fires with a L{Failure}, C{blockingCallFromThread}
        will raise that failure's exception (see L{Failure.raiseException}).
    """
    queue: Queue.Queue[_R | Failure] = Queue.Queue()

    def _callFromThread() -> None:
        result = maybeDeferred(f, *a, **kw)
        result.addBoth(queue.put)

    reactor.callFromThread(_callFromThread)
    result = queue.get()
    if isinstance(result, failure.Failure):
        result.raiseException()
    return result


__all__ = [
    "deferToThread",
    "deferToThreadPool",
    "callMultipleInThread",
    "blockingCallFromThread",
]
