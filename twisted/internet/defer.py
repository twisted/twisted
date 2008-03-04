# -*- test-case-name: twisted.test.test_defer -*-
#
# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Support for results that aren't immediately available.

Maintainer: U{Glyph Lefkowitz<mailto:glyph@twistedmatrix.com>}
"""

from __future__ import nested_scopes, generators
import traceback
import warnings

# Twisted imports
from twisted.python import log, failure, lockfile
from twisted.python.util import unsignedID, mergeFunctionMetadata

class AlreadyCalledError(Exception):
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
    """
    deferred = None

    try:
        result = f(*args, **kw)
    except:
        return fail(failure.Failure())
    else:
        if isinstance(result, Deferred):
            return result
        elif isinstance(result, failure.Failure):
            return fail(result)
        else:
            return succeed(result)
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

def getDebugging():
    """Determine whether Deferred debugging is enabled.
    """
    return Deferred.debug

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
    U{http://twistedmatrix.com/projects/core/documentation/howto/defer.html}
    """
    called = 0
    paused = 0
    timeoutCall = None
    _debugInfo = None

    # Are we currently running a user-installed callback?  Meant to prevent
    # recursive running of callbacks when a reentrant call to add a callback is
    # used.
    _runningCallbacks = False

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
                     errbackArgs=None, errbackKeywords=None):
        """Add a pair of callbacks (success and error) to this Deferred.

        These will be executed when the 'master' callback is run.
        """
        assert callable(callback)
        assert errback == None or callable(errback)
        cbs = ((callback, callbackArgs, callbackKeywords),
               (errback or (passthru), errbackArgs, errbackKeywords))
        self.callbacks.append(cbs)

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
        errback, as appropriate. It is merely a shorthand way of performing
        the following::

            self.addCallbacks(d.callback, d.errback)

        When you chain a deferred d2 to another deferred d1 with
        d1.chainDeferred(d2), you are making d2 participate in the callback
        chain of d1. Thus any event that fires d1 will also fire d2.
        However, the converse is B{not} true; if d2 is fired d1 will not be
        affected.
        """
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
                if self._debugInfo is None:
                    self._debugInfo = DebugInfo()
                extra = "\n" + self._debugInfo._getDebugTracebacks()
                raise AlreadyCalledError(extra)
            raise AlreadyCalledError
        if self.debug:
            if self._debugInfo is None:
                self._debugInfo = DebugInfo()
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
        if self._runningCallbacks:
            # Don't recursively run callbacks
            return
        if not self.paused:
            while self.callbacks:
                item = self.callbacks.pop(0)
                callback, args, kw = item[
                    isinstance(self.result, failure.Failure)]
                args = args or ()
                kw = kw or {}
                try:
                    self._runningCallbacks = True
                    try:
                        self.result = callback(self.result, *args, **kw)
                    finally:
                        self._runningCallbacks = False
                    if isinstance(self.result, Deferred):
                        # note: this will cause _runCallbacks to be called
                        # recursively if self.result already has a result.
                        # This shouldn't cause any problems, since there is no
                        # relevant state in this stack frame at this point.
                        # The recursive call will continue to process
                        # self.callbacks until it is empty, then return here,
                        # where there is no more work to be done, so this call
                        # will return as well.
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

    def setTimeout(self, seconds, timeoutFunc=timeout, *args, **kw):
        """Set a timeout function to be triggered if I am not called.

        @param seconds: How long to wait (from now) before firing the
        timeoutFunc.

        @param timeoutFunc: will receive the Deferred and *args, **kw as its
        arguments.  The default timeoutFunc will call the errback with a
        L{TimeoutError}.
        """
        warnings.warn(
            "Deferred.setTimeout is deprecated.  Look for timeout "
            "support specific to the API you are using instead.",
            DeprecationWarning, stacklevel=2)

        if self.called:
            return
        assert not self.timeoutCall, "Don't call setTimeout twice on the same Deferred."

        from twisted.internet import reactor
        self.timeoutCall = reactor.callLater(
            seconds,
            lambda: self.called or timeoutFunc(self, *args, **kw))
        return self.timeoutCall

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

class FirstError(Exception):
    """First error to occur in a DeferredList if fireOnOneErrback is set.

    @ivar subFailure: the L{Failure} that occurred.
    @ivar index: the index of the Deferred in the DeferredList where it
    happened.
    """
    def __init__(self, failure, index):
        self.subFailure = failure
        self.index = index

    def __repr__(self):
        return 'FirstError(%r, %d)' % (self.subFailure, self.index)

    def __str__(self):
        return repr(self)

    def __getitem__(self, index):
        warnings.warn("FirstError.__getitem__ is deprecated.  "
                      "Use attributes instead.",
                      category=DeprecationWarning, stacklevel=2)
        return [self.subFailure, self.index][index]

    def __getslice__(self, start, stop):
        warnings.warn("FirstError.__getslice__ is deprecated.  "
                      "Use attributes instead.",
                      category=DeprecationWarning, stacklevel=2)
        return [self.subFailure, self.index][start:stop]

    def __eq__(self, other):
        if isinstance(other, tuple):
            return tuple(self) == other
        elif isinstance(other, FirstError):
            return (self.subFailure == other.subFailure and
                    self.index == other.index)
        return False

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

    def _cbDeferred(self, result, index, succeeded):
        """(internal) Callback for when one of my deferreds fires.
        """
        self.resultList[index] = (succeeded, result)

        self.finishedCount += 1
        if not self.called:
            if succeeded == SUCCESS and self.fireOnOneCallback:
                self.callback((result, index))
            elif succeeded == FAILURE and self.fireOnOneErrback:
                self.errback(failure.Failure(FirstError(result, index)))
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

def gatherResults(deferredList):
    """Returns list with result of given Deferreds.

    This builds on C{DeferredList} but is useful since you don't
    need to parse the result for success/failure.

    @type deferredList:  C{list} of L{Deferred}s
    """
    d = DeferredList(deferredList, fireOnOneErrback=1)
    d.addCallback(_parseDListResult)
    return d

# Constants for use with DeferredList

SUCCESS = True
FAILURE = False



## deferredGenerator

class waitForDeferred:
    """
    See L{deferredGenerator}.
    """

    def __init__(self, d):
        if not isinstance(d, Deferred):
            raise TypeError("You must give waitForDeferred a Deferred. You gave it %r." % (d,))
        self.d = d


    def getResult(self):
        if isinstance(self.result, failure.Failure):
            self.result.raiseException()
        return self.result



def _deferGenerator(g, deferred):
    """
    See L{deferredGenerator}.
    """
    result = None

    # This function is complicated by the need to prevent unbounded recursion
    # arising from repeatedly yielding immediately ready deferreds.  This while
    # loop and the waiting variable solve that by manually unfolding the
    # recursion.

    waiting = [True, # defgen is waiting for result?
               None] # result

    while 1:
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
        # they yield a Deferred.
        if isinstance(result, Deferred):
            return fail(TypeError("Yield waitForDeferred(d), not d!"))

        if isinstance(result, waitForDeferred):
            # a waitForDeferred was yielded, get the result.
            # Pass result in so it don't get changed going around the loop
            # This isn't a problem for waiting, as it's only reused if
            # gotResult has already been executed.
            def gotResult(r, result=result):
                result.result = r
                if waiting[0]:
                    waiting[0] = False
                    waiting[1] = r
                else:
                    _deferGenerator(g, deferred)
            result.d.addBoth(gotResult)
            if waiting[0]:
                # Haven't called back yet, set flag so that we get reinvoked
                # and return from the loop
                waiting[0] = False
                return deferred
            # Reset waiting to initial values for next loop
            waiting[0] = True
            waiting[1] = None

            result = None



def deferredGenerator(f):
    """
    Maintainer: U{Christopher Armstrong<mailto:radix@twistedmatrix.com>}

    deferredGenerator and waitForDeferred help you write Deferred-using code
    that looks like a regular sequential function. If your code has a minimum
    requirement of Python 2.5, consider the use of L{inlineCallbacks} instead,
    which can accomplish the same thing in a more concise manner.

    There are two important functions involved: waitForDeferred, and
    deferredGenerator.  They are used together, like this::

        def thingummy():
            thing = waitForDeferred(makeSomeRequestResultingInDeferred())
            yield thing
            thing = thing.getResult()
            print thing #the result! hoorj!
        thingummy = deferredGenerator(thingummy)

    waitForDeferred returns something that you should immediately yield; when
    your generator is resumed, calling thing.getResult() will either give you
    the result of the Deferred if it was a success, or raise an exception if it
    was a failure.  Calling C{getResult} is B{absolutely mandatory}.  If you do
    not call it, I{your program will not work}.

    deferredGenerator takes one of these waitForDeferred-using generator
    functions and converts it into a function that returns a Deferred. The
    result of the Deferred will be the last value that your generator yielded
    unless the last value is a waitForDeferred instance, in which case the
    result will be C{None}.  If the function raises an unhandled exception, the
    Deferred will errback instead.  Remember that 'return result' won't work;
    use 'yield result; return' in place of that.

    Note that not yielding anything from your generator will make the Deferred
    result in None. Yielding a Deferred from your generator is also an error
    condition; always yield waitForDeferred(d) instead.

    The Deferred returned from your deferred generator may also errback if your
    generator raised an exception.  For example::

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

    Put succinctly, these functions connect deferred-using code with this 'fake
    blocking' style in both directions: waitForDeferred converts from a
    Deferred to the 'blocking' style, and deferredGenerator converts from the
    'blocking' style to a Deferred.
    """
    def unwindGenerator(*args, **kwargs):
        return _deferGenerator(f(*args, **kwargs), Deferred())
    return mergeFunctionMetadata(f, unwindGenerator)


## inlineCallbacks

# BaseException is only in Py 2.5.
try:
    BaseException
except NameError:
    BaseException=Exception

class _DefGen_Return(BaseException):
    def __init__(self, value):
        self.value = value

def returnValue(val):
    """
    Return val from a L{inlineCallbacks} generator.

    Note: this is currently implemented by raising an exception
    derived from BaseException.  You might want to change any
    'except:' clauses to an 'except Exception:' clause so as not to
    catch this exception.

    Also: while this function currently will work when called from
    within arbitrary functions called from within the generator, do
    not rely upon this behavior.
    """
    raise _DefGen_Return(val)

def _inlineCallbacks(result, g, deferred):
    """
    See L{inlineCallbacks}.
    """
    # This function is complicated by the need to prevent unbounded recursion
    # arising from repeatedly yielding immediately ready deferreds.  This while
    # loop and the waiting variable solve that by manually unfolding the
    # recursion.

    waiting = [True, # waiting for result?
               None] # result

    while 1:
        try:
            # Send the last result back as the result of the yield expression.
            if isinstance(result, failure.Failure):
                result = result.throwExceptionIntoGenerator(g)
            else:
                result = g.send(result)
        except StopIteration:
            # fell off the end, or "return" statement
            deferred.callback(None)
            return deferred
        except _DefGen_Return, e:
            # returnValue call
            deferred.callback(e.value)
            return deferred
        except:
            deferred.errback()
            return deferred

        if isinstance(result, Deferred):
            # a deferred was yielded, get the result.
            def gotResult(r):
                if waiting[0]:
                    waiting[0] = False
                    waiting[1] = r
                else:
                    _inlineCallbacks(r, g, deferred)

            result.addBoth(gotResult)
            if waiting[0]:
                # Haven't called back yet, set flag so that we get reinvoked
                # and return from the loop
                waiting[0] = False
                return deferred

            result = waiting[1]
            # Reset waiting to initial values for next loop.  gotResult uses
            # waiting, but this isn't a problem because gotResult is only
            # executed once, and if it hasn't been executed yet, the return
            # branch above would have been taken.


            waiting[0] = True
            waiting[1] = None


    return deferred

def inlineCallbacks(f):
    """
    Maintainer: U{Christopher Armstrong<mailto:radix@twistedmatrix.com>}

    WARNING: this function will not work in Python 2.4 and earlier!

    inlineCallbacks helps you write Deferred-using code that looks like a
    regular sequential function. This function uses features of Python 2.5
    generators.  If you need to be compatible with Python 2.4 or before, use
    the L{deferredGenerator} function instead, which accomplishes the same
    thing, but with somewhat more boilerplate.  For example::

        def thingummy():
            thing = yield makeSomeRequestResultingInDeferred()
            print thing #the result! hoorj!
        thingummy = inlineCallbacks(thingummy)

    When you call anything that results in a Deferred, you can simply yield it;
    your generator will automatically be resumed when the Deferred's result is
    available. The generator will be sent the result of the Deferred with the
    'send' method on generators, or if the result was a failure, 'throw'.

    Your inlineCallbacks-enabled generator will return a Deferred object, which
    will result in the return value of the generator (or will fail with a
    failure object if your generator raises an unhandled exception). Note that
    you can't use 'return result' to return a value; use 'returnValue(result)'
    instead. Falling off the end of the generator, or simply using 'return'
    will cause the Deferred to have a result of None.

    The Deferred returned from your deferred generator may errback if your
    generator raised an exception::

        def thingummy():
            thing = yield makeSomeRequestResultingInDeferred()
            if thing == 'I love Twisted':
                # will become the result of the Deferred
                returnValue('TWISTED IS GREAT!')
            else:
                # will trigger an errback
                raise Exception('DESTROY ALL LIFE')
        thingummy = inlineCallbacks(thingummy)
    """
    def unwindGenerator(*args, **kwargs):
        return _inlineCallbacks(None, f(*args, **kwargs), Deferred())
    return mergeFunctionMetadata(f, unwindGenerator)


## DeferredLock/DeferredQueue

class _ConcurrencyPrimitive(object):
    def __init__(self):
        self.waiting = []

    def _releaseAndReturn(self, r):
        self.release()
        return r

    def run(*args, **kwargs):
        """Acquire, run, release.

        This function takes a callable as its first argument and any
        number of other positional and keyword arguments.  When the
        lock or semaphore is acquired, the callable will be invoked
        with those arguments.

        The callable may return a Deferred; if it does, the lock or
        semaphore won't be released until that Deferred fires.

        @return: Deferred of function result.
        """
        if len(args) < 2:
            if not args:
                raise TypeError("run() takes at least 2 arguments, none given.")
            raise TypeError("%s.run() takes at least 2 arguments, 1 given" % (
                args[0].__class__.__name__,))
        self, f = args[:2]
        args = args[2:]

        def execute(ignoredResult):
            d = maybeDeferred(f, *args, **kwargs)
            d.addBoth(self._releaseAndReturn)
            return d

        d = self.acquire()
        d.addCallback(execute)
        return d


class DeferredLock(_ConcurrencyPrimitive):
    """
    A lock for event driven systems.

    @ivar locked: True when this Lock has been acquired, false at all
    other times.  Do not change this value, but it is useful to
    examine for the equivalent of a \"non-blocking\" acquisition.
    """

    locked = 0

    def acquire(self):
        """Attempt to acquire the lock.

        @return: a Deferred which fires on lock acquisition.
        """
        d = Deferred()
        if self.locked:
            self.waiting.append(d)
        else:
            self.locked = 1
            d.callback(self)
        return d

    def release(self):
        """Release the lock.

        Should be called by whomever did the acquire() when the shared
        resource is free.
        """
        assert self.locked, "Tried to release an unlocked lock"
        self.locked = 0
        if self.waiting:
            # someone is waiting to acquire lock
            self.locked = 1
            d = self.waiting.pop(0)
            d.callback(self)

class DeferredSemaphore(_ConcurrencyPrimitive):
    """
    A semaphore for event driven systems.
    """

    def __init__(self, tokens):
        _ConcurrencyPrimitive.__init__(self)
        self.tokens = tokens
        self.limit = tokens

    def acquire(self):
        """Attempt to acquire the token.

        @return: a Deferred which fires on token acquisition.
        """
        assert self.tokens >= 0, "Internal inconsistency??  tokens should never be negative"
        d = Deferred()
        if not self.tokens:
            self.waiting.append(d)
        else:
            self.tokens = self.tokens - 1
            d.callback(self)
        return d

    def release(self):
        """Release the token.

        Should be called by whoever did the acquire() when the shared
        resource is free.
        """
        assert self.tokens < self.limit, "Someone released me too many times: too many tokens!"
        self.tokens = self.tokens + 1
        if self.waiting:
            # someone is waiting to acquire token
            self.tokens = self.tokens - 1
            d = self.waiting.pop(0)
            d.callback(self)

class QueueOverflow(Exception):
    pass

class QueueUnderflow(Exception):
    pass


class DeferredQueue(object):
    """
    An event driven queue.

    Objects may be added as usual to this queue.  When an attempt is
    made to retrieve an object when the queue is empty, a Deferred is
    returned which will fire when an object becomes available.

    @ivar size: The maximum number of objects to allow into the queue
    at a time.  When an attempt to add a new object would exceed this
    limit, QueueOverflow is raised synchronously.  None for no limit.

    @ivar backlog: The maximum number of Deferred gets to allow at
    one time.  When an attempt is made to get an object which would
    exceed this limit, QueueUnderflow is raised synchronously.  None
    for no limit.
    """

    def __init__(self, size=None, backlog=None):
        self.waiting = []
        self.pending = []
        self.size = size
        self.backlog = backlog

    def put(self, obj):
        """Add an object to this queue.

        @raise QueueOverflow: Too many objects are in this queue.
        """
        if self.waiting:
            self.waiting.pop(0).callback(obj)
        elif self.size is None or len(self.pending) < self.size:
            self.pending.append(obj)
        else:
            raise QueueOverflow()

    def get(self):
        """Attempt to retrieve and remove an object from the queue.

        @return: a Deferred which fires with the next object available in the queue.

        @raise QueueUnderflow: Too many (more than C{backlog})
        Deferreds are already waiting for an object from this queue.
        """
        if self.pending:
            return succeed(self.pending.pop(0))
        elif self.backlog is None or len(self.waiting) < self.backlog:
            d = Deferred()
            self.waiting.append(d)
            return d
        else:
            raise QueueUnderflow()


class AlreadyTryingToLockError(Exception):
    """
    Raised when DeferredFilesystemLock.deferUntilLocked is called twice on a
    single DeferredFilesystemLock.
    """


class DeferredFilesystemLock(lockfile.FilesystemLock):
    """
    A FilesystemLock that allows for a deferred to be fired when the lock is
    acquired.

    @ivar _scheduler: The object in charge of scheduling retries. In this
        implementation this is parameterized for testing.

    @ivar _interval: The retry interval for an L{IReactorTime} based scheduler.

    @ivar _tryLockCall: A L{DelayedCall} based on _interval that will managex
        the next retry for aquiring the lock.

    @ivar _timeoutCall: A L{DelayedCall} based on deferUntilLocked's timeout
        argument.  This is in charge of timing out our attempt to acquire the
        lock.
    """
    _interval = 1
    _tryLockCall = None
    _timeoutCall = None

    def __init__(self, name, scheduler=None):
        """
        @param name: The name of the lock to acquire
        @param scheduler: An object which provides L{IReactorTime}
        """
        lockfile.FilesystemLock.__init__(self, name)

        if scheduler is None:
            from twisted.internet import reactor
            scheduler = reactor

        self._scheduler = scheduler

    def deferUntilLocked(self, timeout=None):
        """
        Wait until we acquire this lock.  This method is not safe for
        concurrent use.

        @type timeout: C{float} or C{int}
        @param timeout: the number of seconds after which to time out if the
            lock has not been acquired.

        @return: a deferred which will callback when the lock is acquired, or
            errback with a L{TimeoutError} after timing out or an
            L{AlreadyTryingToLockError} if the L{deferUntilLocked} has already
            been called and not successfully locked the file.
        """
        if self._tryLockCall is not None:
            return fail(
                AlreadyTryingToLockError(
                    "deferUntilLocked isn't safe for concurrent use."))

        d = Deferred()

        def _cancelLock():
            self._tryLockCall.cancel()
            self._tryLockCall = None
            self._timeoutCall = None

            if self.lock():
                d.callback(None)
            else:
                d.errback(failure.Failure(
                        TimeoutError("Timed out aquiring lock: %s after %fs" % (
                                self.name,
                                timeout))))

        def _tryLock():
            if self.lock():
                if self._timeoutCall is not None:
                    self._timeoutCall.cancel()
                    self._timeoutCall = None

                self._tryLockCall = None

                d.callback(None)
            else:
                if timeout is not None and self._timeoutCall is None:
                    self._timeoutCall = self._scheduler.callLater(
                        timeout, _cancelLock)

                self._tryLockCall = self._scheduler.callLater(
                    self._interval, _tryLock)

        _tryLock()

        return d


__all__ = ["Deferred", "DeferredList", "succeed", "fail", "FAILURE", "SUCCESS",
           "AlreadyCalledError", "TimeoutError", "gatherResults",
           "maybeDeferred",
           "waitForDeferred", "deferredGenerator", "inlineCallbacks",
           "DeferredLock", "DeferredSemaphore", "DeferredQueue",
           "DeferredFilesystemLock", "AlreadyTryingToLockError",
          ]
