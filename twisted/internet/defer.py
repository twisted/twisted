# -*- test-case-name: twisted.test.test_defer -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""Support for results that aren't immediately available.

API Stability: stable

Maintainer: U{Glyph Lefkowitz<mailto:glyph@twistedmatrix.com>}
"""

from __future__ import nested_scopes, generators
import traceback
import warnings

# Twisted imports
from twisted.python import log, failure
from twisted.python.util import unsignedID

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
    """
    Return a Deferred that has already had '.callback(result)' called.

    This is useful when you're writing synchronous code to an
    asynchronous interface: i.e., some code is calling you expecting a
    Deferred result, but you don't actually need to do anything
    asynchronous. Just return defer.succeed(theResult).

    See L{fail} for a version of this function that uses a failing
    Deferred rather than a successful one.

    @param result: The result to give to the Deferred's 'callback'
           method.

    @rtype: L{Deferred}
    """
    d = Deferred()
    d.callback(result)
    return d

class _nothing: pass

def fail(result=_nothing):
    """
    Return a Deferred that has already had '.errback(result)' called.

    See L{succeed}'s docstring for rationale.

    @param result: The same argument that L{Deferred.errback<twisted.internet.defer.Deferred.errback>} takes.

    @rtype: L{Deferred}
    """
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
        result = callable(*args, **kw)
    except:
        return fail()
    else:
        return succeed(result)

def maybeDeferred(f, *args, **kw):
    """Invoke a function that may or may not return a deferred.

    Call the given function with the given arguments.  If the returned
    object is a C{Deferred}, return it.  If the returned object is a C{Failure},
    wrap it with C{fail} and return it.  Otherwise, wrap it in C{succeed} and
    return it.  If an exception is raised, convert it to a C{Failure}, wrap it
    in C{fail}, and then return it.

    @type f: Any callable
    @param f: The callable to invoke

    @param args: The arguments to pass to C{f}
    @param kw: The keyword arguments to pass to C{f}

    @rtype: C{Deferred}
    @return: The result of the function call, wrapped in a C{Deferred} if
    necessary.

    API Stability: Unstable
    """
    deferred = None
    if isinstance(f, Deferred) or f is None:
        warnings.warn("First argument to maybeDeferred() should no longer be a Deferred or None.  Just pass the function and the arguments.", DeprecationWarning, stacklevel=2)
        deferred = f or Deferred()
        f = args[0]
        args = args[1:]

    try:
        result = f(*args, **kw)
    except:
        if deferred is None:
            return fail(failure.Failure())
        else:
            deferred.errback(failure.Failure())
    else:
        if isinstance(result, Deferred):
            if deferred is None:
                return result
            else:
                result.chainDeferred(deferred)
        elif isinstance(result, failure.Failure):
            if deferred is None:
                return fail(result)
            else:
                deferred.errback(result)
        else:
            if deferred is None:
                return succeed(result)
            else:
                deferred.callback(result)
    return deferred

def timeout(deferred):
    deferred.errback(failure.Failure(TimeoutError("Callback timed out")))

def passthru(arg):
    return arg

def setDebugging(on):
    """Enable or disable Deferred debugging.

    When debugging is on, the call stacks from creation and invocation are
    recorded, and added to any AlreadyCalledErrors we raise.
    """
    Deferred.debug=bool(on)

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
    timeoutCall = None
    _debugInfo = None

    # Keep this class attribute for now, for compatibility with code that
    # sets it directly.
    debug = False

    def __init__(self):
        self.callbacks = []
        if self.debug:
            self._debugInfo = DebugInfo()
            self._debugInfo.creator = traceback.format_stack()[:-1]

    def addCallbacks(self, callback, errback=None,
                     callbackArgs=None, callbackKeywords=None,
                     errbackArgs=None, errbackKeywords=None, asDefaults=0):
        """Add a pair of callbacks (success and error) to this Deferred.

        These will be executed when the 'master' callback is run.
        """
        assert callable(callback)
        assert errback == None or callable(errback)
        cbs = ((callback, callbackArgs, callbackKeywords),
               (errback or (passthru), errbackArgs, errbackKeywords))
        if self.default:
            self.callbacks[-1] = cbs
        else:
            self.callbacks.append(cbs)
        if asDefaults:
            # what the heck is this crappy argument for?
            warnings.warn("The 'asDefaults' argument will be going away soon. Has anyone ever actually used it?", DeprecationWarning, stacklevel=2)
                
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
        assert not isinstance(result, Deferred)
        self._startRunCallbacks(result)


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

        self._startRunCallbacks(fail)


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

    def _continue(self, result):
        self.result = result
        self.unpause()

    def _startRunCallbacks(self, result):
        if self.called:
            if self.debug:
                extra = "\n" + self._debugInfo._getDebugTracebacks()
                raise AlreadyCalledError(extra)
            raise AlreadyCalledError
        if self.debug:
            self._debugInfo.invoker = traceback.format_stack()[:-2]
        self.called = True
        self.result = result
        if self.timeoutCall:
            try:
                self.timeoutCall.cancel()
            except:
                pass
            
            del self.timeoutCall
        self._runCallbacks()

    def _runCallbacks(self):
        if not self.paused:
            cb = self.callbacks
            self.callbacks = []
            while cb:
                item = cb.pop(0)
                callback, args, kw = item[
                    isinstance(self.result, failure.Failure)]
                args = args or ()
                kw = kw or {}
                try:
                    self.result = callback(self.result, *args, **kw)
                    if isinstance(self.result, Deferred):
                        self.callbacks = cb

                        # note: this will cause _runCallbacks to be called
                        # "recursively" sometimes... this shouldn't cause any
                        # problems, since all the state has been set back to
                        # the way it's supposed to be, but it is useful to know
                        # in case something goes wrong.  deferreds really ought
                        # not to return themselves from their callbacks.
                        self.pause()
                        self.result.addBoth(self._continue)
                        break
                except:
                    self.result = failure.Failure()
            
        if isinstance(self.result, failure.Failure):
            self.result.cleanFailure()
            if self._debugInfo is None:
                self._debugInfo = DebugInfo()
            self._debugInfo.failResult = self.result
        else:
            if self._debugInfo is not None:
                self._debugInfo.failResult = None

    def arm(self):
        """This method is deprecated.
        """
        warnings.warn("Deferred.arm is deprecated, and does nothing. You should stop calling it.", DeprecationWarning, stacklevel=2)

    def setTimeout(self, seconds, timeoutFunc=timeout, *args, **kw):
        """Set a timeout function to be triggered if I am not called.

        @param seconds: How long to wait (from now) before firing the
        timeoutFunc.

        @param timeoutFunc: will receive the Deferred and *args, **kw as its
        arguments.  The default timeoutFunc will call the errback with a
        L{TimeoutError}.

        DON'T USE THIS! It's a bad idea! Use a function called by reactor.callLater instead
        to accomplish the same thing!

        YOU HAVE BEEN WARNED!
        """

        if self.called:
            return
        assert not self.timeoutCall, "Don't call setTimeout twice on the same Deferred."

        from twisted.internet import reactor
        self.timeoutCall = reactor.callLater(
            seconds,
            lambda: self.called or timeoutFunc(self, *args, **kw))
        return self.timeoutCall

    def armAndErrback(self, fail=None):
        warnings.warn("Deferred.armAndErrback is deprecated. You should be calling .errback instead.", DeprecationWarning, stacklevel=2)
        return self.errback(fail)

    def armAndCallback(self, result):
        warnings.warn("Deferred.armAndErrback is deprecated. You should be calling .callback instead.", DeprecationWarning, stacklevel=2)
        return self.callback(result)

    def armAndChain(self, d):
        warnings.warn("Deferred.armAndChain is deprecated. You should be calling .chainDeferred instead.", DeprecationWarning, stacklevel=2)
        return self.chainDeferred(d)

    def __str__(self):
        cname = self.__class__.__name__
        if hasattr(self, 'result'):
            return "<%s at %s  current result: %r>" % (cname, hex(unsignedID(self)),
                                                       self.result)
        return "<%s at %s>" % (cname, hex(unsignedID(self)))
    __repr__ = __str__

class DebugInfo:
    """Deferred debug helper"""
    failResult = None

    def _getDebugTracebacks(self):
        info = ''
        if hasattr(self, "creator"):
            info += " C: Deferred was created:\n C:"
            info += "".join(self.creator).rstrip().replace("\n","\n C:")
            info += "\n"
        if hasattr(self, "invoker"):
            info += " I: First Invoker was:\n I:"
            info += "".join(self.invoker).rstrip().replace("\n","\n I:")
            info += "\n"
        return info

    def __del__(self):
        """Print tracebacks and die.

        If the *last* (and I do mean *last*) callback leaves me in an error
        state, print a traceback (if said errback is a Failure).
        """
        if self.failResult is not None:
            log.msg("Unhandled error in Deferred:", isError=True)
            debugInfo = self._getDebugTracebacks()
            if debugInfo != '':
                log.msg("(debug: " + debugInfo + ")", isError=True)
            log.err(self.failResult)

class DeferredList(Deferred):
    """I combine a group of deferreds into one callback.

    I track a list of L{Deferred}s for their callbacks, and make a single
    callback when they have all completed, a list of (success, result)
    tuples, 'success' being a boolean.

    Note that you can still use a L{Deferred} after putting it in a
    DeferredList.  For example, you can suppress 'Unhandled error in Deferred'
    messages by adding errbacks to the Deferreds *after* putting them in the
    DeferredList, as a DeferredList won't swallow the errors.  (Although a more
    convenient way to do this is simply to set the consumeErrors flag)
    """

    fireOnOneCallback = 0
    fireOnOneErrback = 0

    def __init__(self, deferredList, fireOnOneCallback=0, fireOnOneErrback=0,
                 consumeErrors=0):
        """Initialize a DeferredList.

        @type deferredList:  C{list} of L{Deferred}s
        @param deferredList: The list of deferreds to track.
        @param fireOnOneCallback: (keyword param) a flag indicating that
                             only one callback needs to be fired for me to call
                             my callback
        @param fireOnOneErrback: (keyword param) a flag indicating that
                            only one errback needs to be fired for me to call
                            my errback
        @param consumeErrors: (keyword param) a flag indicating that any errors
                            raised in the original deferreds should be
                            consumed by this DeferredList.  This is useful to
                            prevent spurious warnings being logged.
        """
        self.resultList = [None] * len(deferredList)
        Deferred.__init__(self)
        if len(deferredList) == 0 and not fireOnOneCallback:
            self.callback(self.resultList)

        # These flags need to be set *before* attaching callbacks to the
        # deferreds, because the callbacks use these flags, and will run
        # synchronously if any of the deferreds are already fired.
        self.fireOnOneCallback = fireOnOneCallback
        self.fireOnOneErrback = fireOnOneErrback
        self.consumeErrors = consumeErrors
        self.finishedCount = 0

        index = 0
        for deferred in deferredList:
            deferred.addCallbacks(self._cbDeferred, self._cbDeferred,
                                  callbackArgs=(index,SUCCESS),
                                  errbackArgs=(index,FAILURE))
            index = index + 1

    def addDeferred(self, deferred):
        """DEPRECATED"""
        warnings.warn('DeferredList.addDeferred is deprecated.',
                      DeprecationWarning, stacklevel=2)
        self.resultList.append(None)
        index = len(self.resultList) - 1
        deferred.addCallbacks(self._cbDeferred, self._cbDeferred,
                              callbackArgs=(index,SUCCESS),
                              errbackArgs=(index,FAILURE))

    def _cbDeferred(self, result, index, succeeded):
        """(internal) Callback for when one of my deferreds fires.
        """
        self.resultList[index] = (succeeded, result)

        self.finishedCount += 1
        if not self.called:
            if succeeded == SUCCESS and self.fireOnOneCallback:
                self.callback((result, index))
            elif succeeded == FAILURE and self.fireOnOneErrback:
                self.errback(failure.Failure((result, index)))
            elif self.finishedCount == len(self.resultList):
                self.callback(self.resultList)

        if succeeded == FAILURE and self.consumeErrors:
            result = None

        return result


def _parseDListResult(l, fireOnOneErrback=0):
    if __debug__:
        for success, value in l:
            assert success
    return [x[1] for x in l]

def gatherResults(deferredList, fireOnOneErrback=0):
    """Returns list with result of given Deferreds.

    This builds on C{DeferredList} but is useful since you don't
    need to parse the result for success/failure.

    @type deferredList:  C{list} of L{Deferred}s
    """
    if fireOnOneErrback:
        raise "This function was previously totally, totally broken.  Please fix your code to behave as documented."
    d = DeferredList(deferredList, fireOnOneErrback=1)
    d.addCallback(_parseDListResult)
    return d

# Constants for use with DeferredList

SUCCESS = True
FAILURE = False




class waitForDeferred:
    """
    API Stability: semi-stable

    Maintainer: U{Christopher Armstrong<mailto:radix@twistedmatrix.com>}
    
    waitForDeferred and deferredGenerator help you write
    Deferred-using code that looks like it's blocking (but isn't
    really), with the help of generators.

    There are two important functions involved: waitForDeferred, and
    deferredGenerator.

        def thingummy():
            thing = waitForDeferred(makeSomeRequestResultingInDeferred())
            yield thing
            thing = thing.getResult()
            print thing #the result! hoorj!
        thingummy = deferredGenerator(thingummy)

    waitForDeferred returns something that you should immediately yield;
    when your generator is resumed, calling thing.getResult() will either
    give you the result of the Deferred if it was a success, or raise an
    exception if it was a failure.

    deferredGenerator takes one of these waitForDeferred-using
    generator functions and converts it into a function that returns a
    Deferred. The result of the Deferred will be the last
    value that your generator yielded (remember that 'return result' won't
    work; use 'yield result; return' in place of that).

    Note that not yielding anything from your generator will make the
    Deferred result in None. Yielding a Deferred from your generator
    is also an error condition; always yield waitForDeferred(d)
    instead.

    The Deferred returned from your deferred generator may also
    errback if your generator raised an exception.

        def thingummy():
            thing = waitForDeferred(makeSomeRequestResultingInDeferred())
            yield thing
            thing = thing.getResult()
            if thing == 'I love Twisted':
                # will become the result of the Deferred
                yield 'TWISTED IS GREAT!'
                return
            else:
                # will trigger an errback
                raise Exception('DESTROY ALL LIFE')
        thingummy = deferredGenerator(thingummy)

    Put succinctly, these functions connect deferred-using code with this
    'fake blocking' style in both directions: waitForDeferred converts from
    a Deferred to the 'blocking' style, and deferredGenerator converts from
    the 'blocking' style to a Deferred.
    """
    def __init__(self, d):
        if not isinstance(d, Deferred):
            raise TypeError("You must give waitForDeferred a Deferred. You gave it %r." % (d,))
        self.d = d

    def getResult(self):
        if hasattr(self, 'failure'):
            self.failure.raiseException()
        return self.result

def _deferGenerator(g, deferred=None, result=None):
    """
    See L{waitForDeferred}.
    """
    if deferred is None:
        deferred = Deferred()
    try:
        result = g.next()
    except StopIteration:
        deferred.callback(result)
        return deferred
    except:
        deferred.errback()
        return deferred

    # Deferred.callback(Deferred) raises an error; we catch this case
    # early here and give a nicer error message to the user in case
    # they yield a Deferred. Perhaps eventually these semantics may
    # change.
    if isinstance(result, Deferred):
        return fail(TypeError("Yield waitForDeferred(d), not d!"))

    if isinstance(result, waitForDeferred):
        def gotResult(r):
            result.result = r
            _deferGenerator(g, deferred, r)
        def gotError(f):
            result.failure = f
            _deferGenerator(g, deferred, f)
        result.d.addCallbacks(gotResult, gotError)
    else:
        _deferGenerator(g, deferred, result)
    return deferred

def deferredGenerator(f):
    """
    See L{waitForDeferred}.
    """
    return lambda *args, **kwargs: _deferGenerator(f(*args, **kwargs))



__all__ = ["Deferred", "DeferredList", "succeed", "fail", "FAILURE", "SUCCESS",
           "AlreadyCalledError", "TimeoutError", "gatherResults",
           "maybeDeferred", "waitForDeferred", "deferredGenerator",
          ]
