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


# Twisted imports
from twisted.python import log, failure

# System Imports
import types

class AlreadyCalledError(Exception):
    pass

class AlreadyArmedError(Exception):
    pass

class TimeoutError(Exception):
    pass

def logError(err):
    log.err(err)
    return err

def _sched(m, r):
    from twisted.internet import reactor
    reactor.callLater(0, m, r)

def succeed(result):
    d = Deferred()
    d.callback(result)
    return d

def fail(result):
    d = Deferred()
    d.errback(result)
    return d

def timeout(deferred):
    deferred.errback(failure.Failure(TimeoutError("Callback timed out")))


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

    called = 0
    default = 0
    paused = 0

    def __init__(self):
        self.callbacks = []

    def addCallbacks(self, callback, errback=None,
                     callbackArgs=None, callbackKeywords=None,
                     errbackArgs=None, errbackKeywords=None, asDefaults=0):
        """Add a pair of callbacks (success and error) to this Deferred.

        These will be executed when the 'master' callback is run.
        """
        cbs = ((callback, callbackArgs, callbackKeywords),
               (errback or logError, errbackArgs, errbackKeywords))
        if self.default:
            self.callbacks[-1] = cbs
        else:
            self.callbacks.append(cbs)
        self.default = asDefaults
        if self.called:
            self._runCallbacks()
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

    def callback(self, result):
        """Run all success callbacks that have been added to this Deferred.

        Each callback will have its result passed as the first
        argument to the next; this way, the callbacks act as a
        'processing chain'.

        If this deferred has not been armed yet, nothing will happen until it
        is armed.
        """
        self._startRunCallbacks(result, 0)


    def errback(self, fail=None):
        """Run all error callbacks that have been added to this Deferred.

        Each callback will have its result passed as the first
        argument to the next; this way, the callbacks act as a
        'processing chain'.

        If this deferred has not been armed yet, nothing will happen until it
        is armed.
        """
        if not fail:
            fail = failure.Failure()
        self._startRunCallbacks(fail, 1)


    def pause(self):
        """Stop processing on a Deferred until unpause() is called.
        """
        self.paused = 1


    def unpause(self):
        """Process all callbacks made since pause() was called.
        """
        self.paused = 0
        if self.called:
            self._runCallbacks()


    def _startRunCallbacks(self, result, isError):
        if self.called:
            raise AlreadyCalledError()
        self.called = isError + 1
        self.isError = isError
        self.result = result
        self._runCallbacks()


    def _runCallbacks(self):
        if self.paused:
            return
        cb = self.callbacks
        self.callbacks = []
        for item in cb:
            callback, args, kw = item[self.isError]
            args = args or ()
            kw = kw or {}
            try:
                self.result = apply(callback, (self.result,)+tuple(args), kw)
                if type(self.result) != types.StringType:
                    # TODO: make this hack go away; it has something to do
                    # with PB returning strings from errbacks that are
                    # actually tracebacks that we still want to handle as
                    # errors sometimes... can't find exactly where right
                    # now
                    if not isinstance(self.result, failure.Failure):
                        self.isError = 0
            except:
                self.result = failure.Failure()
                self.isError = 1
                # if this was the last pair of callbacks, we must make sure
                # that the error was logged, otherwise we'll never hear about
                # it.
                if item is cb[-1]:
                    logError(self.result)


    def arm(self):
        """This method is deprecated.
        """
        pass

    def setTimeout(self, seconds, timeoutFunc=timeout):
        """Set a timeout function to be triggered if I am not called.

        timeoutFunc will receive the Deferred as its only argument.  The 
        default timeoutFunc will call the errback with a TimeoutError.

        The timeout counts down from when this method is called.
        """
        from twisted.internet import reactor
        reactor.callLater(seconds, 
                          lambda s=self, f=timeoutFunc: s.called or f(s))

    armAndErrback = errback
    armAndCallback = callback
    armAndChain = chainDeferred


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

    def _cbDeferred(self, result, index, succeeded):
        """(internal) Callback for when one of my deferreds fires.
        """
        self.resultList[index] = (succeeded, result)
        if not (None in self.resultList):
            self.callback(self.resultList)


# Constants for use with DeferredList

SUCCESS = 1
FAILURE = 0

__all__ = ["Deferred", "DeferredList", "succeed", "fail", "FAILURE", "SUCCESS"]

