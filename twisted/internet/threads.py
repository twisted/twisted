# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""Extended thread dispatching support.

For basic support see reactor threading API docs.

API Stability: stable

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
"""

# twisted imports
from twisted.python import log, failure

# sibling imports
from twisted.internet import defer


def _putResultInDeferred(deferred, f, args, kwargs):
    """Run a function and give results to a Deferred."""
    from twisted.internet import reactor
    try:
        result = f(*args, **kwargs)
    except:
        f = failure.Failure()
        reactor.callFromThread(deferred.errback, f)
    else:
        reactor.callFromThread(deferred.callback, result)

def deferToThread(f, *args, **kwargs):
    """Run function in thread and return result as Deferred."""
    d = defer.Deferred()
    from twisted.internet import reactor
    reactor.callInThread(_putResultInDeferred, d, f, args, kwargs)
    return d


def _runMultiple(tupleList):
    """Run a list of functions."""
    for f, args, kwargs in tupleList:
        f(*args, **kwargs)

def callMultipleInThread(tupleList):
    """Run a list of functions in the same thread.

    tupleList should be a list of (function, argsList, kwargsDict) tuples.
    """
    from twisted.internet import reactor
    reactor.callInThread(_runMultiple, tupleList)


__all__ = ["deferToThread", "callMultipleInThread"]
