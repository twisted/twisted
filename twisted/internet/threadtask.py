# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
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

"""A thread pool that is integrated with the Twisted event loop."""

import sys

# Sibling Import
import task, main

# Twisted Import
from twisted.python import threadpool, threadable, log, failure

threadable.init(1)

class ThreadDispatcher(threadpool.ThreadPool):
    """A thread pool that is integrated with the Twisted event loop.

    The difference from ThreadPool is that callbacks are run in the main IO
    event loop thread, and are thus inherently thread-safe.

    You probably want your instance to be shutdown when Twisted is shut down:

        from twisted.internet import main
        from twisted.internet import threadtask
        tpool = ThreadDispatcher()
        main.callDuringShutdown(tpool.stop)

    """

    def __init__(self, *args, **kwargs):
        apply(threadpool.ThreadPool.__init__, (self,) + args, kwargs)
        main.callWhenRunning(self.start)
        self._callbacks = []

    def _runWithCallback(self, callback, errback, func, args, kwargs):
        try:
            result = apply(func, args, kwargs)
        except:
            task.schedule(errback, failure.Failure())
        else:
            task.schedule(callback, result)

    def dispatchWithCallback(self, owner, callback, errback, func, *args, **kw):
        """Dispatch a function, returning the result to a callback function.

        The callback function will be called in the main event loop thread.
        """
        self.dispatchApply(owner, callback, errback, func, args, kw)

    def dispatchApply(self, owner, callback, errback, func, args, kw):
        self.dispatch(owner, self._runWithCallback, callback, errback, func, args, kw)

    def runInThread(self, callback, errback, func, *args, **kw):
        self.dispatchApply(log.logOwner.owner(), callback, errback, func, args, kw)

    def stop(self):
        log.msg("stopping thread dispatcher " +str(self))
        threadpool.ThreadPool.stop(self)


theDispatcher = ThreadDispatcher(0)

def dispatchApply(callback, errback, func, args, kw):
    theDispatcher.dispatchApply(log.logOwner.owner(), callback, errback, func, args, kw)

def dispatch(callback, errback, func, *args, **kw):
    dispatchApply(callback, errback, func, args, kw)

main.callDuringShutdown(theDispatcher.stop)
