# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""Thread dispatching support."""

# twisted imports
from twisted.python import threadable, log, failure

# sibling imports
import defer

# this will get initialized when threading is enabled
theThreadPool = None

def initThreading():
    """Called the first time callInThread is called."""
    from twisted.python import threadpool
    from twisted.internet import reactor
    threadable.init(1)
    
    global theThreadPool
    theThreadPool = threadpool.ThreadPool(0, 10)
    theThreadPool.start()
    reactor.addSystemEventTrigger('during', 'shutdown', theThreadPool.stop)

def shutdown():
    """Close the thread pool."""
    if theThreadPool:
        theThreadPool.stop()


def suggestThreadPoolSize(size):
    """Suggest the maximum size of the thread pool."""
    if not theThreadPool:
        initThreading()
    oldSize = theThreadPool.max
    theThreadPool.max = size
    if oldSize > size:
        import threadpool
        for i in range(oldSize - size):
            theThreadPool.q.put(threadpool.WorkerStop)
    else:
        theThreadPool._startSomeWorkers()


def callInThread(f, *args, **kwargs):
    """Run a function in a separate thread."""
    if not theThreadPool:
        initThreading()
    apply(theThreadPool.dispatch, (log.logOwner.owner(), f) + args, kwargs)


def _putResultInDeferred(deferred, f, args, kwargs):
    """Run a function and give results to a Deferred."""
    from twisted.internet import reactor
    try:
        result = apply(f, args, kwargs)
    except:
        f = failure.Failure()
        reactor.callFromThread(deferred.errback, f)
    else:
        reactor.callFromThread(deferred.callback, result)

def deferToThread(f, *args, **kwargs):
    """Run function in thread and return result as Deferred."""
    d = defer.Deferred()
    callInThread(_putResultInDeferred, d, f, args, kwargs)
    return d


def _runMultiple(tupleList):
    """Run a list of functions."""
    for f, args, kwargs in tupleList:
        apply(f, args, kwargs)

def callMultipleInThread(tupleList):
    """Run a list of functions in the same thread.

    tupleList should be a list of (function, argsList, kwargsDict) tuples.
    """
    callInThread(_runMultiple, tupleList)


__all__ = ["suggestThreadPoolSize", "callInThread", "deferToThread", "callMultipleInThread"]
