

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


# System Imports
import types
import sys

class AlreadyArmedError(Exception):
    pass

def logError(err):
    if isinstance(err, failure.Failure):
        err.printTraceback(log)
    else:
        log.msg(str(err))
    return err

def _sched(m):
    from twisted.internet import task
    task.schedule(m)

def succeed(result):
    d = Deferred()
    d.callback(result)
    _sched(d.arm)
    return d

def fail(result):
    d = Deferred()
    d.errback(result)
    _sched(d.arm)
    return d


class Deferred:
    """This is a callback which will be put off until later.

    Why do we want this? Well, in cases where a function in a threaded
    program would block until it gets a result, for Twisted it should
    not block. Instead, it should return a Deferred.

    This can be implemented for protocols that run over the network by
    writing an asynchronous protocol for twisted.internet. For methods
    that come from outside packages that are not under our control, we use
    threads (see for example twisted.enterprise.adbapi).
    """

    armed = 0
    #self.called: 0 = "not called"; 1 = "answered", 2 = "errored"
    called = 0
    default = 0

    def __init__(self):
        self.callbacks = []

    def addCallbacks(self, callback, errback=None,
                     callbackArgs=None, callbackKeywords=None,
                     errbackArgs=None, errbackKeywords=None, asDefaults=0):
        """Add a pair of callbacks (success and error) to this Deferred.

        These will be executed when the 'master' callback is run.
        """
        if self.armed:
            raise AlreadyArmedError("You cannot add callbacks after a deferred"
                                    "has already been armed.")
        cbs = ((callback, callbackArgs, callbackKeywords),
               (errback or logError, errbackArgs, errbackKeywords))
        if self.default:
            self.callbacks[-1] = cbs
        else:
            self.callbacks.append(cbs)
        self.default = asDefaults
        return self

    def addCallback(self, callback, *args, **kw):
        """Convenience method for adding just a callback.

        See addCallbacks.
        """
        return self.addCallbacks(callback, callbackArgs=args,
                                 callbackKeywords=kw)

    def addErrback(self, errback, *args, **kw):
        """Convenience method for adding just an errback.

        See addCallbacks.
        """
        return self.addCallbacks(lambda x: x, errback,
                                 errbackArgs=args,
                                 errbackKeywords=kw)

    def addBoth(self, callback, *args, **kw):
        """Convenience method for adding a single callable as both a callback
        and an errback.

        See addCallbacks.
        """
        return self.addCallbacks(callback, callback,
                                 callbackArgs=args, errbackArgs=args,
                                 callbackKeywords=kw, errbackKeywords=kw)

    def chainDeferred(self, d):
        return self.addCallbacks(d.callback, d.errback)

    def armAndCallback(self, result):
        """Utility method to arm me and immediately issue a callback.
        """
        self.arm()
        return self._runCallbacks(result, 0)

    def armAndErrback(self, error):
        """Utility method to arm me and immediately issue an error callback.
        """
        self.arm()
        return self._runCallbacks(error, 1)

    def armAndChain(self, deferred):
        """Utility method to add another deferred to me as a set of callbacks.

        Arguments:

          deferred: the Deferred to be armed and fired when my callback arrives.
        """
        return self.addCallbacks(deferred.armAndCallback, deferred.armAndErrback)

    def callback(self, result):
        """Run all success callbacks that have been added to this Deferred.

        Each callback will have its result passed as the first
        argument to the next; this way, the callbacks act as a
        'processing chain'.

        If this deferred has not been armed yet, nothing will happen until it
        is armed.
        """
        return self._runCallbacks(result, 0)


    def errback(self, error):
        """Run all error callbacks that have been added to this Deferred.

        Each callback will have its result passed as the first
        argument to the next; this way, the callbacks act as a
        'processing chain'.

        If this deferred has not been armed yet, nothing will happen until it
        is armed.
        """
        return self._runCallbacks(error, 1)

    def _runCallbacks(self, result, isError):
        self.called = isError + 1
        if self.armed:
            for item in self.callbacks:
                callback, args, kw = item[isError]
                args = args or ()
                kw = kw or {}
                try:
                    result = apply(callback, (result,)+tuple(args), kw)
                    if type(result) != types.StringType:
                        # TODO: make this hack go away; it has something to do
                        # with PB returning strings from errbacks that are
                        # actually tracebacks that we still want to handle as
                        # errors sometimes... can't find exactly where right
                        # now
                        if not isinstance(result, failure.Failure):
                            isError = 0
                except:
                    result = failure.Failure()
                    isError = 1
                    # if this was the last pair of callbacks, we must make sure
                    # that the error was logged, otherwise we'll never hear about it.
                    if item == self.callbacks[-1]:
                        logError(result)
        else:
            self.cbResult = result


    def arm(self):
        #start doing callbacks whenever you're ready, Mr. Deferred.
        """State that this function is ready to be called.

        This is to prevent callbacks from being executed sometimes
        synchronously and sometimes asynchronously.  The system
        expecting a Deferred will explicitly arm the delayed after
        it has been returned; at _that_ point, it may fire later.
        """
        if not self.armed:
            self.armed = 1
            if self.called:
                #'self.called - 1' is so self.called won't be changed.
                self._runCallbacks(self.cbResult, self.called - 1)
##        else:
##            log.msg("WARNING: double-arming deferred.")


class DeferredList(Deferred):
    """I combine a group of deferreds into one callback.

    I track a list of Deferreds for their callbacks, and make a single
    callback when they have all completed.
    """
    def __init__(self, deferredList):
        """Initialize a DeferredList.

        Arguments::

          deferredList: a list of Deferreds
        """
        self.resultList = [None] * len(deferredList)
        Deferred.__init__(self)
        index = 0
        for deferred in deferredList:
            deferred.addCallbacks(self._cbDeferred, self._cbDeferred,
                                  callbackArgs=(index,SUCCESS),
                                  errbackArgs=(index,FAILURE))
            index = index + 1
            deferred.arm()

    def _cbDeferred(self, result, index, succeeded):
        """(internal) Callback for when one of my deferreds fires.
        """
        self.resultList[index] = (succeeded, result)
        if not (None in self.resultList):
            self.callback(self.resultList)


# Constants for use with DeferredList

SUCCESS = 1
FAILURE = 0

__all__ = ["Deferred", "DeferredList", "succeed", "fail"]

# Sibling Imports
import log
import failure
