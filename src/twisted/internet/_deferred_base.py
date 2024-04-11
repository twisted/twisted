import os

try:
    import cython
except ImportError:

    class cython:
        # Match real module's behavior in interpreted mode when it is
        # installed.
        compiled = False

        @staticmethod
        def declare(type, **kwargs):
            return {bool: False, int: 0, object: None}[type]

        @staticmethod
        def cclass(klass):
            return klass

        ccall = cclass
        cfunc = cclass

        bint = bool
        int = int
        object = object


import traceback
from enum import Enum
from types import MappingProxyType
from typing import (
    Any,
    Callable,
    List,
    Mapping,
    Optional,
    Tuple,
    Union,
)

from typing_extensions import Literal

from twisted.logger import Logger
from twisted.python.deprecate import warnAboutFunction
from twisted.python.failure import Failure
from ._deferred_shared import DebugInfo, AlreadyCalledError, CancelledError

log = Logger()


class _Sentinel(Enum):
    """
    @cvar _NO_RESULT:
        The result used to represent the fact that there is no result.
        B{Never ever ever use this as an actual result for a Deferred}.
        You have been warned.
    @cvar _CONTINUE:
        A marker left in L{Deferred.callback}s to indicate a Deferred chain.
        Always accompanied by a Deferred instance in the args tuple pointing at
        the Deferred which is chained to the Deferred which has this marker.
    """

    _NO_RESULT = object()
    _CONTINUE = object()


# Cache these values for use without the extra lookup in deferred hot code paths
_NO_RESULT = _Sentinel._NO_RESULT
_CONTINUE = _Sentinel._CONTINUE


# type note: this should be Callable[[object, ...], object] but mypy doesn't allow.
#     Callable[[object], object] is next best, but disallows valid callback signatures
DeferredCallback = Callable[..., object]
# type note: this should be Callable[[Failure, ...], object] but mypy doesn't allow.
#     Callable[[Failure], object] is next best, but disallows valid callback signatures
DeferredErrback = Callable[..., object]

_CallbackOrderedArguments = Tuple[object, ...]
_CallbackKeywordArguments = Mapping[str, object]
_CallbackChain = Tuple[
    Tuple[
        Union[DeferredCallback, Literal[_Sentinel._CONTINUE]],
        _CallbackOrderedArguments,
        _CallbackKeywordArguments,
    ],
    Tuple[
        Union[DeferredErrback, DeferredCallback, Literal[_Sentinel._CONTINUE]],
        _CallbackOrderedArguments,
        _CallbackKeywordArguments,
    ],
]

_NONE_KWARGS: _CallbackKeywordArguments = MappingProxyType({})


def _failthru(arg: Failure) -> Failure:
    return arg


@cython.cfunc
def passthru(arg: object) -> object:
    return arg


@cython.cclass
class _DeferredBase:
    """
    This is a callback which will be put off until later.

    Why do we want this? Well, in cases where a function in a threaded
    program would block until it gets a result, for Twisted it should
    not block. Instead, it should return a L{Deferred}.

    This can be implemented for protocols that run over the network by
    writing an asynchronous protocol for L{twisted.internet}. For methods
    that come from outside packages that are not under our control, we use
    threads (see for example L{twisted.enterprise.adbapi}).

    For more information about Deferreds, see doc/core/howto/defer.html or
    U{http://twistedmatrix.com/documents/current/core/howto/defer.html}

    When creating a Deferred, you may provide a canceller function, which
    will be called by d.cancel() to let you do any clean-up necessary if the
    user decides not to wait for the deferred to complete.

    @ivar called: A flag which is C{False} until either C{callback} or
        C{errback} is called and afterwards always C{True}.
    @ivar paused: A counter of how many unmatched C{pause} calls have been made
        on this instance.
    @ivar _suppressAlreadyCalled: A flag used by the cancellation mechanism
        which is C{True} if the Deferred has no canceller and has been
        cancelled, C{False} otherwise.  If C{True}, it can be expected that
        C{callback} or C{errback} will eventually be called and the result
        should be silently discarded.
    @ivar _runningCallbacks: A flag which is C{True} while this instance is
        executing its callback chain, used to stop recursive execution of
        L{_runCallbacks}
    @ivar _chainedTo: If this L{Deferred} is waiting for the result of another
        L{Deferred}, this is a reference to the other Deferred.  Otherwise,
        L{None}.
    """

    called = cython.declare(cython.bint, visibility="public")
    paused = cython.declare(cython.int, visibility="public")
    _debugInfo = cython.declare(object, visibility="public")
    _suppressAlreadyCalled = cython.declare(object, visibility="public")
    callbacks = cython.declare(object, visibility="public")
    _canceller = cython.declare(object, visibility="public")
    result = cython.declare(object, visibility="public")

    # Are we currently running a user-installed callback?  Meant to prevent
    # recursive running of callbacks when a reentrant call to add a callback is
    # used.
    _runningCallbacks = cython.declare(cython.bint, visibility="public")

    # Keep this class attribute for now, for compatibility with code that
    # sets it directly.
    debug = False

    _chainedTo = cython.declare(object, visibility="public")

    def __init__(self, canceller=None):
        """
        Initialize a L{Deferred}.

        @param canceller: a callable used to stop the pending operation
            scheduled by this L{Deferred} when L{Deferred.cancel} is invoked.
            The canceller will be passed the deferred whose cancellation is
            requested (i.e., C{self}).

            If a canceller is not given, or does not invoke its argument's
            C{callback} or C{errback} method, L{Deferred.cancel} will
            invoke L{Deferred.errback} with a L{CancelledError}.

            Note that if a canceller is not given, C{callback} or
            C{errback} may still be invoked exactly once, even though
            defer.py will have already invoked C{errback}, as described
            above.  This allows clients of code which returns a L{Deferred}
            to cancel it without requiring the L{Deferred} instantiator to
            provide any specific implementation support for cancellation.
            New in 10.1.

        @type canceller: a 1-argument callable which takes a L{Deferred}. The
            return result is ignored.
        """
        self.callbacks: List[_CallbackChain] = []
        self._canceller = canceller
        self.called = False
        self.paused = 0
        self._debugInfo = None
        self._suppressAlreadyCalled = False
        self._runningCallbacks = False
        self._chainedTo = None

        if self.debug:
            self._debugInfo = DebugInfo()
            self._debugInfo.creator = traceback.format_stack()[:-1]

    @cython.ccall
    def addCallbacks(
        self,
        callback,
        errback=None,
        callbackArgs=(),
        callbackKeywords=_NONE_KWARGS,
        errbackArgs=(),
        errbackKeywords=_NONE_KWARGS,
    ):
        """
        Add a pair of callbacks (success and error) to this L{Deferred}.

        These will be executed when the 'master' callback is run.

        @note: The signature of this function was designed many years before
            PEP 612; ParamSpec provides no mechanism to annotate parameters
            like C{callbackArgs}; this is therefore inherently less type-safe
            than calling C{addCallback} and C{addErrback} separately.

        @return: C{self}.
        """
        if errback is None:
            errback = _failthru

        # Default value used to be None and callers may be using None
        if callbackArgs is None:
            callbackArgs = ()  # type: ignore[unreachable]
        if callbackKeywords is None:
            callbackKeywords = {}  # type: ignore[unreachable]
        if errbackArgs is None:
            errbackArgs = ()  # type: ignore[unreachable]
        if errbackKeywords is None:
            errbackKeywords = {}  # type: ignore[unreachable]

        self.callbacks.append(
            (
                (callback, callbackArgs, callbackKeywords),
                (errback, errbackArgs, errbackKeywords),
            )
        )

        if self.called:
            self._runCallbacks()

        # type note: The Deferred's type has changed here, but *idiomatically*
        #     the caller should treat the result as the new type, consistently.
        return self  # type:ignore[return-value]

    # BEGIN way too many @overload-s for addCallback, addErrback, and addBoth:
    # these must be accomplished with @overloads, rather than a big Union on
    # the result type as you might expect, because the fact that
    # _NextResultT has no bound makes mypy get confused and require the
    # return types of functions to be combinations of Deferred and Failure
    # rather than the actual return type.  I'm not entirely sure what about the
    # semantics of <nothing> create this overzealousness on the part of trying
    # to assign a type; there *might* be a mypy bug in there somewhere.
    # Possibly https://github.com/python/typing/issues/548 is implicated here
    # because TypeVar for the *callable* with a variadic bound might express to
    # Mypy the actual constraint that we want on its type.

    def addCallback(self, callback: Any, *args: Any, **kwargs: Any):
        """
        Convenience method for adding just a callback.

        See L{addCallbacks}.
        """
        # Implementation Note: Any annotations for brevity; the overloads above
        # handle specifying the actual signature, and there's nothing worth
        # type-checking in this implementation.
        return self.addCallbacks(callback, callbackArgs=args, callbackKeywords=kwargs)

    def addErrback(self, errback: Any, *args: Any, **kwargs: Any):
        """
        Convenience method for adding just an errback.

        See L{addCallbacks}.
        """
        # See implementation note in addCallbacks about Any arguments
        return self.addCallbacks(
            passthru, errback, errbackArgs=args, errbackKeywords=kwargs
        )

    def addBoth(self, callback: Any, *args: Any, **kwargs: Any):
        """
        Convenience method for adding a single callable as both a callback
        and an errback.

        See L{addCallbacks}.
        """
        # See implementation note in addCallbacks about Any arguments
        return self.addCallbacks(
            callback,
            callback,
            callbackArgs=args,
            errbackArgs=args,
            callbackKeywords=kwargs,
            errbackKeywords=kwargs,
        )

    # END way too many overloads

    def chainDeferred(self, d):
        """
        Chain another L{Deferred} to this L{Deferred}.

        This method adds callbacks to this L{Deferred} to call C{d}'s callback
        or errback, as appropriate. It is merely a shorthand way of performing
        the following::

            d1.addCallbacks(d2.callback, d2.errback)

        When you chain a deferred C{d2} to another deferred C{d1} with
        C{d1.chainDeferred(d2)}, you are making C{d2} participate in the
        callback chain of C{d1}.
        Thus any event that fires C{d1} will also fire C{d2}.
        However, the converse is B{not} true; if C{d2} is fired, C{d1} will not
        be affected.

        Note that unlike the case where chaining is caused by a L{Deferred}
        being returned from a callback, it is possible to cause the call
        stack size limit to be exceeded by chaining many L{Deferred}s
        together with C{chainDeferred}.

        @return: C{self}.
        """
        d._chainedTo = self
        return self.addCallbacks(d.callback, d.errback)

    @cython.ccall
    def callback(self, result):
        """
        Run all success callbacks that have been added to this L{Deferred}.

        Each callback will have its result passed as the first argument to
        the next; this way, the callbacks act as a 'processing chain'.  If
        the success-callback returns a L{Failure} or raises an L{Exception},
        processing will continue on the *error* callback chain.  If a
        callback (or errback) returns another L{Deferred}, this L{Deferred}
        will be chained to it (and further callbacks will not run until that
        L{Deferred} has a result).

        An instance of L{Deferred} may only have either L{callback} or
        L{errback} called on it, and only once.

        @param result: The object which will be passed to the first callback
            added to this L{Deferred} (via L{addCallback}), unless C{result} is
            a L{Failure}, in which case the behavior is the same as calling
            C{errback(result)}.

        @raise AlreadyCalledError: If L{callback} or L{errback} has already been
            called on this L{Deferred}.
        """
        self._startRunCallbacks(result)

    @cython.ccall
    def errback(self, fail: Optional[Union[Failure, BaseException]] = None):
        """
        Run all error callbacks that have been added to this L{Deferred}.

        Each callback will have its result passed as the first
        argument to the next; this way, the callbacks act as a
        'processing chain'. Also, if the error-callback returns a non-Failure
        or doesn't raise an L{Exception}, processing will continue on the
        *success*-callback chain.

        If the argument that's passed to me is not a L{Failure} instance,
        it will be embedded in one. If no argument is passed, a
        L{Failure} instance will be created based on the current
        traceback stack.

        Passing a string as `fail' is deprecated, and will be punished with
        a warning message.

        An instance of L{Deferred} may only have either L{callback} or
        L{errback} called on it, and only once.

        @param fail: The L{Failure} object which will be passed to the first
            errback added to this L{Deferred} (via L{addErrback}).
            Alternatively, a L{Exception} instance from which a L{Failure} will
            be constructed (with no traceback) or L{None} to create a L{Failure}
            instance from the current exception state (with a traceback).

        @raise AlreadyCalledError: If L{callback} or L{errback} has already been
            called on this L{Deferred}.
        @raise NoCurrentExceptionError: If C{fail} is L{None} but there is
            no current exception state.
        """
        if fail is None:
            fail = Failure(captureVars=self.debug)
        elif not isinstance(fail, Failure):
            fail = Failure(fail)

        self._startRunCallbacks(fail)

    def pause(self):
        """
        Stop processing on a L{Deferred} until L{unpause}() is called.
        """
        self.paused = self.paused + 1

    def unpause(self):
        """
        Process all callbacks made since L{pause}() was called.
        """
        self.paused = self.paused - 1
        if self.paused:
            return None
        if self.called:
            self._runCallbacks()

    def cancel(self):
        """
        Cancel this L{Deferred}.

        If the L{Deferred} has not yet had its C{errback} or C{callback} method
        invoked, call the canceller function provided to the constructor. If
        that function does not invoke C{callback} or C{errback}, or if no
        canceller function was provided, errback with L{CancelledError}.

        If this L{Deferred} is waiting on another L{Deferred}, forward the
        cancellation to the other L{Deferred}.
        """
        if not self.called:
            canceller = self._canceller
            if canceller:
                canceller(self)
            else:
                # Arrange to eat the callback that will eventually be fired
                # since there was no real canceller.
                self._suppressAlreadyCalled = True
            if not self.called:
                # There was no canceller, or the canceller didn't call
                # callback or errback.
                self.errback(Failure(CancelledError()))
        elif isinstance(self.result, _DeferredBase):
            # Waiting for another deferred -- cancel it instead.
            self.result.cancel()

    @cython.cfunc
    def _startRunCallbacks(self, result: object):
        if self.called:
            if self._suppressAlreadyCalled:
                self._suppressAlreadyCalled = False
                return None
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

        # Clear the canceller to avoid any circular references. This is safe to
        # do as the canceller does not get called after the deferred has fired
        self._canceller = None

        self.result = result
        self._runCallbacks()

    @cython.cfunc
    def _continuation(self):
        """
        Build a tuple of callback and errback with L{_Sentinel._CONTINUE}.
        """
        return (
            (_Sentinel._CONTINUE, (self,), _NONE_KWARGS),
            (_Sentinel._CONTINUE, (self,), _NONE_KWARGS),
        )

    @cython.cfunc
    def _runCallbacks(self):
        """
        Run the chain of callbacks once a result is available.

        This consists of a simple loop over all of the callbacks, calling each
        with the current result and making the current result equal to the
        return value (or raised exception) of that call.

        If L{_runningCallbacks} is true, this loop won't run at all, since
        it is already running above us on the call stack.  If C{self.paused} is
        true, the loop also won't run, because that's what it means to be
        paused.

        The loop will terminate before processing all of the callbacks if a
        L{Deferred} without a result is encountered.

        If a L{Deferred} I{with} a result is encountered, that result is taken
        and the loop proceeds.

        @note: The implementation is complicated slightly by the fact that
            chaining (associating two L{Deferred}s with each other such that one
            will wait for the result of the other, as happens when a Deferred is
            returned from a callback on another L{Deferred}) is supported
            iteratively rather than recursively, to avoid running out of stack
            frames when processing long chains.
        """
        if self._runningCallbacks:
            # Don't recursively run callbacks
            return None

        # Keep track of all the Deferreds encountered while propagating results
        # up a chain.  The way a Deferred gets onto this stack is by having
        # added its _continuation() to the callbacks list of a second Deferred
        # and then that second Deferred being fired.  ie, if ever had _chainedTo
        # set to something other than None, you might end up on this stack.
        chain = [self]

        while chain:
            current = chain[-1]

            if current.paused:
                # This Deferred isn't going to produce a result at all.  All the
                # Deferreds up the chain waiting on it will just have to...
                # wait.
                return None

            finished = True
            current._chainedTo = None
            while current.callbacks:
                item = current.callbacks.pop(0)
                if not isinstance(current.result, Failure):
                    callback, args, kwargs = item[0]
                else:
                    # type note: Callback signature also works for Errbacks in
                    #     this context.
                    callback, args, kwargs = item[1]

                # Avoid recursion if we can.
                if callback is _CONTINUE:
                    # Give the waiting Deferred our current result and then
                    # forget about that result ourselves.
                    chainee = args[0]
                    chainee.result = current.result
                    current.result = None
                    # Making sure to update _debugInfo
                    if current._debugInfo is not None:
                        current._debugInfo.failResult = None
                    chainee.paused -= 1
                    chain.append(chainee)
                    # Delay cleaning this Deferred and popping it from the chain
                    # until after we've dealt with chainee.
                    finished = False
                    break

                try:
                    current._runningCallbacks = True
                    try:
                        # type note: mypy sees `callback is _CONTINUE` above and
                        #    then decides that `callback` is not callable.
                        #    This goes away when we use `_Sentinel._CONTINUE`
                        #    instead, but we don't want to do that attribute
                        #    lookup in this hot code path, so we ignore the mypy
                        #    complaint here.
                        current.result = callback(  # type: ignore[misc]
                            current.result, *args, **kwargs
                        )

                        if current.result is current:
                            warnAboutFunction(
                                callback,
                                "Callback returned the Deferred "
                                "it was attached to; this breaks the "
                                "callback chain and will raise an "
                                "exception in the future.",
                            )
                    finally:
                        current._runningCallbacks = False
                except BaseException:
                    # Including full frame information in the Failure is quite
                    # expensive, so we avoid it unless self.debug is set.
                    current.result = Failure(captureVars=self.debug)
                else:
                    if isinstance(current.result, _DeferredBase):
                        # The result is another Deferred.  If it has a result,
                        # we can take it and keep going.
                        resultResult = getattr(current.result, "result", _NO_RESULT)
                        if (
                            resultResult is _NO_RESULT
                            or isinstance(resultResult, _DeferredBase)
                            or current.result.paused
                        ):
                            # Nope, it didn't.  Pause and chain.
                            current.pause()
                            current._chainedTo = current.result
                            # Note: current.result has no result, so it's not
                            # running its callbacks right now.  Therefore we can
                            # append to the callbacks list directly instead of
                            # using addCallbacks.
                            current.result.callbacks.append(current._continuation())
                            break
                        else:
                            # Yep, it did.  Steal it.
                            current.result.result = None
                            # Make sure _debugInfo's failure state is updated.
                            if current.result._debugInfo is not None:
                                current.result._debugInfo.failResult = None
                            current.result = resultResult

            if finished:
                # As much of the callback chain - perhaps all of it - as can be
                # processed right now has been.  The current Deferred is waiting on
                # another Deferred or for more callbacks.  Before finishing with it,
                # make sure its _debugInfo is in the proper state.
                if isinstance(current.result, Failure):
                    # Stash the Failure in the _debugInfo for unhandled error
                    # reporting.
                    current.result.cleanFailure()
                    if current._debugInfo is None:
                        current._debugInfo = DebugInfo()
                    current._debugInfo.failResult = current.result
                else:
                    # Clear out any Failure in the _debugInfo, since the result
                    # is no longer a Failure.
                    if current._debugInfo is not None:
                        current._debugInfo.failResult = None

                # This Deferred is done, pop it from the chain and move back up
                # to the Deferred which supplied us with our result.
                chain.pop()
