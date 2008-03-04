# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Extended thread dispatching support.

For basic support see reactor threading API docs.

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
"""

import Queue

from twisted.python import failure
from twisted.internet import defer


def _putResultInDeferred(deferred, f, args, kwargs):
    """
    Run a function and give results to a Deferred.
    """
    from twisted.internet import reactor
    try:
        result = f(*args, **kwargs)
    except:
        f = failure.Failure()
        reactor.callFromThread(deferred.errback, f)
    else:
        reactor.callFromThread(deferred.callback, result)


def deferToThread(f, *args, **kwargs):
    """
    Run function in thread and return result as Deferred.
    """
    d = defer.Deferred()
    from twisted.internet import reactor
    reactor.callInThread(_putResultInDeferred, d, f, args, kwargs)
    return d


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
    from twisted.internet import reactor
    reactor.callInThread(_runMultiple, tupleList)


def blockingCallFromThread(reactor, f, *a, **kw):
    """
    Run a function in the reactor from a thread, and wait for the result
    synchronously, i.e. until the callback chain returned by the function
    get a result.

    @param reactor: The L{IReactorThreads} provider which will be used to
        schedule the function call.
    @param f: the callable to run in the reactor thread
    @type f: any callable.
    @param a: the arguments to pass to C{f}.
    @param kw: the keyword arguments to pass to C{f}.

    @return: the result of the callback chain.
    @raise: any error raised during the callback chain.
    """
    queue = Queue.Queue()
    def _callFromThread():
        result = defer.maybeDeferred(f, *a, **kw)
        result.addBoth(queue.put)
    reactor.callFromThread(_callFromThread)
    result = queue.get()
    if isinstance(result, failure.Failure):
        result.raiseException()
    return result


__all__ = ["deferToThread", "callMultipleInThread", "blockingCallFromThread"]

