# -*- test-case-name: twisted.test.test_defer -*-
#
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

"""Support for results that aren't immediately available.

API Stability: stable

Maintainer: U{Glyph Lefkowitz<mailto:glyph@twistedmatrix.com>}
"""

# Twisted imports
from twisted.python import log, failure


class AlreadyCalledError(Exception):
    pass

class AlreadyArmedError(Exception):
    pass

class TimeoutError(Exception):
    pass

def logError(err):
    log.err(err)
    return err

def succeed(result):
    d = Deferred()
    d.callback(result)
    return d

class _nothing: pass

def fail(result=_nothing):
    if result is _nothing:
        result = failure.Failure()
    d = Deferred()
    d.errback(result)
    return d

def execute(callable, *args, **kw):
    """Create a deferred from a callable and arguments.

    Call the given function with the given arguments.  Return a deferred which
    has been fired with its callback as the result of that invocation or its
    errback with a Failure for the exception thrown.
    """
    try:
        result = apply(callable, args, kw)
    except:
        return fail()
    else:
        return succeed(result)


def timeout(deferred):
    deferred.errback(failure.Failure(TimeoutError("Callback timed out")))

def passthru(arg):
    return arg

class Deferred:
    """This is a callback which will be put off until later.

    Why do we want this? Well, in cases where a function in a threaded
    program would block until it gets a result, for Twisted it should
    not block. Instead, it should return a Deferred.

    This can be implemented for protocols that run over the network by
    writing an asynchronous protocol for twisted.internet. For methods
    that come from outside packages that are not under our control, we use
    threads (see for example L{twisted.enterprise.adbapi}).

    For more information about Deferreds, see doc/howto/defer.html or
    U{http://www.twistedmatrix.com/documents/howto/defer}
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
               (errback or (passthru), errbackArgs, errbackKeywords))
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

        See L{addCallbacks}.
        """
        return self.addCallbacks(callback, callbackArgs=args,
                                 callbackKeywords=kw)

    def addErrback(self, errback, *args, **kw):
        """Convenience method for adding just an errback.

        See L{addCallbacks}.
        """
        return self.addCallbacks(passthru, errback,
                                 errbackArgs=args,
                                 errbackKeywords=kw)

    def addBoth(self, callback, *args, **kw):
        """Convenience method for adding a single callable as both a callback
        and an errback.

        See L{addCallbacks}.
        """
        return self.addCallbacks(callback, callback,
                                 callbackArgs=args, errbackArgs=args,
                                 callbackKeywords=kw, errbackKeywords=kw)

    def chainDeferred(self, d):
        """Chain another Deferred to this Deferred.

        This method adds callbacks to this Deferred to call d's callback or
        errback, as appropriate."""
        return self.addCallbacks(d.callback, d.errback)

    def callback(self, result):
        """Run all success callbacks that have been added to this Deferred.

        Each callback will have its result passed as the first
        argument to the next; this way, the callbacks act as a
        'processing chain'. Also, if the success-callback returns a Failure
        or raises an Exception, processing will continue on the *error*-
        callback chain.
        """
        self._startRunCallbacks(result, 0)


    def errback(self, fail=None):
        """Run all error callbacks that have been added to this Deferred.

        Each callback will have its result passed as the first
        argument to the next; this way, the callbacks act as a
        'processing chain'. Also, if the error-callback returns a non-Failure
        or doesn't raise an Exception, processing will continue on the
        *success*-callback chain.

        If the argument that's passed to me is not a failure.Failure instance,
        it will be embedded in one. If no argument is passed, a failure.Failure
        instance will be created based on the current traceback stack.

        Passing a string as `fail' is deprecated, and will be punished with
        a warning message.
        """
        if not isinstance(fail, failure.Failure):
            fail = failure.Failure(fail)

        self._startRunCallbacks(fail, 1)


    def pause(self):
        """Stop processing on a Deferred until L{unpause}() is called.
        """
        self.paused = self.paused + 1


    def unpause(self):
        """Process all callbacks made since L{pause}() was called.
        """
        self.paused = self.paused - 1
        if self.paused:
            return
        if self.called:
            self._runCallbacks()

    def _continue(self, result, isError):
        self.result = result
        self.isError = isError
        self.unpause()

    def _startRunCallbacks(self, result, isError):
        if self.called:
            raise AlreadyCalledError()
        self.called = isError + 1
        self.isError = isError
        self.result = result
        self._runCallbacks()


    def _runCallbacks(self):
        if not self.paused:
            cb = self.callbacks
            self.callbacks = []
            while cb:
                item = cb.pop(0)
                callback, args, kw = item[self.isError]
                args = args or ()
                kw = kw or {}
                try:
                    self.result = apply(callback,
                                        (self.result,)+tuple(args), kw)
                    if isinstance(self.result, Deferred):
                        self.callbacks = cb

                        # note: this will cause _runCallbacks to be called
                        # "recursively" sometimes... this shouldn't cause any
                        # problems, since all the state has been set back to
                        # the way it's supposed to be, but it is useful to know
                        # in case something goes wrong.  deferreds really ought
                        # not to return themselves from their callbacks.
                        self.pause()
                        self.result.addCallbacks(self._continue,
                                                 self._continue,
                                                 callbackArgs=(0,),
                                                 errbackArgs=(1,))
                        break
                    if not isinstance(self.result, failure.Failure):
                        self.isError = 0
                except:
                    self.result = failure.Failure()
                    self.isError = 1
        if self.isError and isinstance(self.result, failure.Failure):
            self.result.cleanFailure()


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


    def __str__(self):
        if hasattr(self, 'result'):
            return "<Deferred at %s  current result: %r>" % (hex(id(self)),
                                                            self.result)
        return "<Deferred at %s>" % hex(id(self))
    __repr__ = __str__
        

    def __del__(self):
        """Print tracebacks and die.

        If the *last* (and I do mean *last*) callback leaves me in an error
        state, print a traceback (if said errback is a Failure).
        """
        if (self.called and
            self.isError and
            isinstance(self.result, failure.Failure)):
            log.msg("Unhandled error in Deferred:")
            log.err(self.result)


class DeferredList(Deferred):
    """I combine a group of deferreds into one callback.

    I track a list of L{Deferred}s for their callbacks, and make a single
    callback when they have all completed.
    """

    fireOnOneCallback = 0
    fireOnOneErrback = 0

    def __init__(self, deferredList, fireOnOneCallback=0, fireOnOneErrback=0):
        """Initialize a DeferredList.

        @type deferredList:  C{list} of L{Deferred}s
        @param deferredList: The list of deferreds to track.
        @param fireOnOneCallback: (keyword param) a flag indicating that
                             only one callback needs to
                             be fired for me to call my callback
        @param fireOnOneErrback: (keyword param) a flag indicating that
                            only one errback needs to be fired for me to
                            call my errback
        """
        self.resultList = [None] * len(deferredList)
        Deferred.__init__(self)
        index = 0
        for deferred in deferredList:
            deferred.addCallbacks(self._cbDeferred, self._cbDeferred,
                                  callbackArgs=(index,SUCCESS),
                                  errbackArgs=(index,FAILURE))
            index = index + 1

        self.fireOnOneCallback = fireOnOneCallback
        self.fireOnOneErrback = fireOnOneErrback

    def addDeferred(self, deferred):
        self.resultList.append(None)
        index = len(self.resultList) - 1
        deferred.addCallbacks(self._cbDeferred, self._cbDeferred,
                                  callbackArgs=(index,SUCCESS),
                                  errbackArgs=(index,FAILURE))
        
    def _cbDeferred(self, result, index, succeeded):
        """(internal) Callback for when one of my deferreds fires.
        """
        self.resultList[index] = (succeeded, result)

        if not self.called:
            if succeeded == SUCCESS and self.fireOnOneCallback:
                self.callback((result, index))
            elif succeeded == FAILURE and self.fireOnOneErrback:
                self.errback(failure.Failure((result, index)))
            elif None not in self.resultList:
                self.callback(self.resultList)




# Constants for use with DeferredList

SUCCESS = 1
FAILURE = 0

__all__ = ["Deferred", "DeferredList", "succeed", "fail", "FAILURE", "SUCCESS",
           "AlreadyCalledError", "TimeoutError"]
